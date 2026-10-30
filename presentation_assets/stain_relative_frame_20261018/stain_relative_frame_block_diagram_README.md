# Stain-Relative Coordinates

English, picture-first, 16:9 block diagram for a presentation. The main sequence is **Detect -> Center -> Align -> Generate -> Restore**. Text is limited to stage names, symbols and short scope labels. Geometry, point clouds, strip angle and polishing strokes are illustrative; they are not experimental data.

## Files

- `stain_relative_frame_block_diagram.png`: 3840 x 2160, white background, ready for PowerPoint.
- `stain_relative_frame_block_diagram.svg`: portable vector, with fonts converted to paths.
- `stain_relative_frame_block_diagram.pdf`: vector PDF.
- `stain_relative_frame_block_diagram_source.py`: editable drawing source.
- `stain_relative_frame_block_diagram_provenance.json`: implementation sources and output hashes.

The earlier text-heavy version is retained in `previous_text_version/` in the thesis workspace. Only this figure, its source and its evidence notes were revised; the thesis manuscript and PDF were not changed. No robot execution, model training or new evaluation was performed.

## Diagram semantics

- **Detect:** the implemented dark-region registration maps image points to base XY using planar homography, estimates a robust center and an SVD axis, then freezes the center and optional angle for the episode. The picture condenses detection and registration into one panel.
- **Center:** subtract the frozen live center `c` from the observed TCP XY position.
- **Align:** when enabled, rotate relative XY by `alpha = wrap_pi(theta_ref - theta_live)`. The small camera/rotation icon represents the separate optional RGB rotation about the TCP-ROI center, with the configured image-coordinate sign.
- **Generate:** image, pose/state (`q`) and measured-force history condition the Flow policy. Normalization and action denormalization remain as implemented but are omitted from the illustration. The waveform is an input-modality icon, not a measured force trace.
- **Restore:** rotate generated XY by `-alpha`, then add the same frozen center `c`. The executor receives base-coordinate positions. The colored stroke is a schematic output path.
- **Train:** subtract `c_demo` from demonstration observation and action XY. Training-data conversion does not rotate episodes. The matrix icon represents learned parameters; it is not an architecture diagram or a numerical weight plot.

`wrap_pi(delta) = ((delta + pi/2) mod pi) - pi/2`. The stain axis has a 180-degree period. `theta_ref` is a configured teaching-reference angle, not a policy-estimated quantity. The illustrated horizontal reference and strip tilt are schematic; they do not specify the runtime reference angle or a tested rotation range.

`z`, the tool rotation-vector channels (`rho`), and force channels (`F`) are unchanged **by the XY coordinate adapter**. The policy can still generate changing Z, orientation and target force. Their existing preprocessing, numerical normalization and coordinate conventions remain in place. `F*` denotes generated target force; the waveform entering Flow denotes measured force/history.

Disabled direction alignment, a missing angle, or an angle outside the configured range retains translation-only operation (`alpha=0`). Direction alignment was OFF in the reported E1/E2 comparisons. This figure illustrates the implemented transfer mechanism and makes no measured position/direction-generalization claim.

## Regenerate

Use the existing Python environment with Matplotlib and NumPy:

```bash
python3 stain_relative_frame_block_diagram_source.py --output-dir .
```

An optional `--repo /home/eunseop/nrs_imitation` records implementation-file hashes. The generator does not modify those files or import ROS, policies, checkpoints or datasets. PNG layout and SVG/PDF output were checked after revision; labels contain no Korean text.
