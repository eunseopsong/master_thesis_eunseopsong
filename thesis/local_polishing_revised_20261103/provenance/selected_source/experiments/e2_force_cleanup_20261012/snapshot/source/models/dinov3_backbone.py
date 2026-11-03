#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""DINOv3 dense image features and TCP-ROI pooling helpers."""

from __future__ import annotations

from contextlib import nullcontext
from typing import Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F


def build_fixed_tcp_roi_mask(
    image: torch.Tensor,
    *,
    reference_width: int = 424,
    reference_height: int = 240,
    center_x: int = 253,
    center_y: int = 120,
    area_fraction: float = 0.10,
) -> torch.Tensor:
    """Build a per-batch square TCP ROI mask directly from image geometry."""
    if image.dim() != 4:
        raise RuntimeError(f"image must be (B,C,H,W), got {tuple(image.shape)}")
    batch, _, height, width = image.shape
    ref_w = int(reference_width)
    ref_h = int(reference_height)
    fraction = float(area_fraction)
    if ref_w <= 0 or ref_h <= 0:
        raise ValueError(f"TCP ROI reference resolution must be positive, got {ref_w}x{ref_h}")
    if not (0.0 < fraction <= 1.0):
        raise ValueError(f"tcp_roi_area_fraction must be in (0,1], got {fraction}")

    cx = float(center_x) * float(width) / float(ref_w)
    cy = float(center_y) * float(height) / float(ref_h)
    side = max(1, int(round((float(width * height) * fraction) ** 0.5)))
    x0 = max(0, min(width - 1, int(round(cx)) - side // 2))
    y0 = max(0, min(height - 1, int(round(cy)) - side // 2))
    x1 = min(width, x0 + side)
    y1 = min(height, y0 + side)
    # Preserve the requested size when clipping against the far edge.
    x0 = max(0, x1 - side)
    y0 = max(0, y1 - side)

    mask = image.new_zeros((batch, 1, height, width))
    mask[:, :, y0:y1, x0:x1] = 1.0
    return mask


class DINOv3PatchBackbone(nn.Module):
    """
    Thin timm DINOv3 wrapper returning a CLS feature and spatial patch map.

    Inputs are expected to be normalized already. Images are padded on the
    right/bottom to a patch-size multiple; zero padding therefore represents
    the normalization mean instead of a black RGB border.
    """

    def __init__(
        self,
        *,
        model_name: str = "vit_small_patch16_dinov3.lvd1689m",
        pretrained: bool = True,
        freeze: bool = True,
        checkpoint_path: str = "",
    ) -> None:
        super().__init__()
        try:
            import timm
        except ImportError as exc:
            raise RuntimeError(
                "DINOv3 requires timm>=1.0.20. Install it with "
                "`python3 -m pip install 'timm>=1.0.20,<2'`."
            ) from exc

        create_kwargs = {
            "pretrained": bool(pretrained and not checkpoint_path),
            "num_classes": 0,
            "dynamic_img_size": True,
        }
        if checkpoint_path:
            create_kwargs["checkpoint_path"] = str(checkpoint_path)
        self.model = timm.create_model(str(model_name), **create_kwargs)
        self.model_name = str(model_name)
        self.freeze = bool(freeze)
        self.feature_dim = int(getattr(self.model, "num_features", getattr(self.model, "embed_dim")))
        patch_size = getattr(self.model.patch_embed, "patch_size", (16, 16))
        if isinstance(patch_size, int):
            patch_size = (patch_size, patch_size)
        self.patch_size = (int(patch_size[0]), int(patch_size[1]))
        self.num_prefix_tokens = int(getattr(self.model, "num_prefix_tokens", 1))

        if self.freeze:
            self.model.requires_grad_(False)
            self.model.eval()

    def train(self, mode: bool = True):
        super().train(mode)
        if self.freeze:
            self.model.eval()
        return self

    def forward(self, image: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor, Tuple[int, int]]:
        if image.dim() != 4:
            raise RuntimeError(f"DINOv3 image must be (B,3,H,W), got {tuple(image.shape)}")
        _, channels, height, width = image.shape
        if channels != 3:
            raise RuntimeError(f"DINOv3 expects 3 RGB channels, got {channels}")

        patch_h, patch_w = self.patch_size
        pad_h = (-height) % patch_h
        pad_w = (-width) % patch_w
        padded = F.pad(image, (0, pad_w, 0, pad_h)) if (pad_h or pad_w) else image

        ctx = torch.no_grad() if self.freeze else nullcontext()
        with ctx:
            tokens = self.model.forward_features(padded)
        if not torch.is_tensor(tokens) or tokens.dim() != 3:
            raise RuntimeError(
                f"Expected DINOv3 forward_features() to return (B,N,C), got {type(tokens)} "
                f"shape={getattr(tokens, 'shape', None)}"
            )

        grid_h = padded.shape[-2] // patch_h
        grid_w = padded.shape[-1] // patch_w
        expected_patches = grid_h * grid_w
        patch_tokens = tokens[:, self.num_prefix_tokens :]
        if patch_tokens.shape[1] != expected_patches:
            raise RuntimeError(
                "DINOv3 patch-token count mismatch: "
                f"got {patch_tokens.shape[1]}, expected {grid_h}x{grid_w}={expected_patches}; "
                f"prefix_tokens={self.num_prefix_tokens}"
            )

        global_feature = tokens[:, 0]
        patch_map = patch_tokens.transpose(1, 2).reshape(
            image.shape[0], self.feature_dim, grid_h, grid_w
        )
        return global_feature, patch_map, (pad_h, pad_w)


class ROIPatchAttentionPool(nn.Module):
    """Learnable attention pooling over spatial tokens selected by a soft ROI."""

    def __init__(self, feature_dim: int, *, empty_mode: str = "global") -> None:
        super().__init__()
        mode = str(empty_mode).strip().lower()
        if mode not in ("zero", "global"):
            raise ValueError(f"empty_mode must be zero or global, got {empty_mode}")
        self.empty_mode = mode
        self.score = nn.Sequential(
            nn.LayerNorm(int(feature_dim)),
            nn.Linear(int(feature_dim), 1),
        )

    def forward(
        self,
        patch_map: torch.Tensor,
        roi_mask: torch.Tensor,
        *,
        global_feature: Optional[torch.Tensor] = None,
        threshold: float = 0.5,
        pad_hw: Tuple[int, int] = (0, 0),
        eps: float = 1e-6,
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        if patch_map.dim() != 4:
            raise RuntimeError(f"patch_map must be (B,C,H,W), got {tuple(patch_map.shape)}")
        mask = roi_mask.float()
        if mask.dim() == 3:
            mask = mask.unsqueeze(1)
        elif mask.dim() == 5 and mask.size(1) == 1:
            mask = mask[:, 0]
        if mask.dim() != 4 or mask.size(1) != 1:
            raise RuntimeError(f"roi_mask must be (B,1,H,W) or (B,H,W), got {tuple(roi_mask.shape)}")
        if float(mask.detach().max().item()) > 1.5:
            mask = mask / 255.0
        mask = (mask.clamp(0.0, 1.0) >= float(threshold)).to(dtype=patch_map.dtype)
        pad_h, pad_w = (int(pad_hw[0]), int(pad_hw[1]))
        if pad_h or pad_w:
            mask = F.pad(mask, (0, pad_w, 0, pad_h))

        roi_weights = F.interpolate(mask, size=patch_map.shape[-2:], mode="area")
        tokens = patch_map.flatten(2).transpose(1, 2)
        weights = roi_weights.flatten(2).transpose(1, 2)
        roi_sum = weights.sum(dim=1)
        empty = roi_sum < float(eps)

        logits = self.score(tokens) + weights.clamp_min(float(eps)).log()
        logits = logits.masked_fill(weights <= 0.0, -torch.finfo(logits.dtype).max)
        attention = torch.softmax(logits, dim=1)
        pooled = (tokens * attention).sum(dim=1)

        if empty.any():
            if self.empty_mode == "global":
                fallback = global_feature if global_feature is not None else tokens.mean(dim=1)
            else:
                fallback = torch.zeros_like(pooled)
            pooled = torch.where(empty, fallback, pooled)

        return pooled, roi_weights, roi_sum
