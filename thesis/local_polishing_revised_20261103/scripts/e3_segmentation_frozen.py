"""Verbatim pure functions from the frozen E3 analyzer; original SHA-256: 27c3ab769dd55fe2102ff028c0c4cdf8cec88834abaedda7ba70bf40d022ece5"""
import cv2
import numpy as np

def polygon_mask(shape, polygons):
    mask = np.zeros(shape[:2], np.uint8)
    for polygon in polygons:
        if polygon:
            cv2.fillPoly(mask, [np.asarray(polygon, np.int32)], 1)
    return mask.astype(bool)

def dilate(mask, radius):
    if not radius:
        return mask.copy()
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (radius * 2 + 1, radius * 2 + 1))
    return cv2.dilate(mask.astype(np.uint8), kernel).astype(bool)

def warp_image(image, matrix, shape, nearest=False):
    return cv2.warpPerspective(image, matrix, (shape[1], shape[0]),
        flags=cv2.INTER_NEAREST if nearest else cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT, borderValue=0)

def stable_mask(shape, alternate_initial=False):
    # Only invariant, rigid plate features. Central moving tool AND its reflection
    # and every target position are excluded from feature extraction.
    if alternate_initial:
        # The pre-execution camera is shifted; its invariant labels/slash are
        # further left. Exclude the underlying lower plate (different plane).
        mask=polygon_mask(shape, [[[104,15],[179,15],[179,123],[104,123]],
                                  [[310,10],[365,10],[365,115],[310,115]]])
    else:
        mask = polygon_mask(shape, [[[116, 31], [406, 31], [358, 139], [143, 139]]])
        mask[28:149, 223:332] = False
    return mask.astype(np.uint8) * 255

def align(before, after, pair, config):
    gray_b = cv2.cvtColor(before, cv2.COLOR_RGB2GRAY)
    gray_a = cv2.cvtColor(after, cv2.COLOR_RGB2GRAY)
    patch_checks = []
    if not pair['used_alternative_image'] and not pair['after_is_near_abort_not_HOME']:
        radius = config['alignment']['search_radius_px']
        for x, y, w, h in config['alignment']['patches_xywh']:
            template = gray_b[y:y+h, x:x+w]
            search = gray_a[y-radius:y+h+radius, x-radius:x+w+radius]
            score = cv2.matchTemplate(search, template, cv2.TM_CCOEFF_NORMED)
            _, maximum, _, location = cv2.minMaxLoc(score)
            patch_checks.append(dict(rect_xywh=[x,y,w,h], dx_after_px=location[0]-radius,
                dy_after_px=location[1]-radius, ncc=float(maximum),
                background_median_before=float(np.median(template)),
                background_median_after=float(np.median(gray_a[y:y+h,x:x+w]))))
        valid = [p for p in patch_checks if p['ncc'] >= config['alignment']['minimum_patch_ncc']]
        if len(valid) >= config['alignment']['required_same_shift_patches'] and all(p['dx_after_px'] == p['dy_after_px'] == 0 for p in valid):
            return np.eye(3), dict(method='identity_verified_by_immutable_surface_patches', valid=True,
                after_to_before_homography=np.eye(3).tolist(), patch_checks=patch_checks,
                scale_change=1.0, resampling='none', landmark_shift_px=[0,0],
                reason='All five independent fixed plate patches peak at exactly zero native-pixel displacement. Robot, stain and reflections are not registration references.')
    # A different view is used only in the six occluded cases. Fit a surface-plane
    # homography to stable plate features, never to disappearing ink or the robot.
    cv2.setRNGSeed(0)
    detector = cv2.SIFT_create(nfeatures=3500, contrastThreshold=.008, edgeThreshold=12)
    kb, db = detector.detectAndCompute(gray_b, stable_mask(gray_b.shape,pair['used_alternative_image']))
    ka, da = detector.detectAndCompute(gray_a, stable_mask(gray_a.shape))
    assert da is not None and db is not None
    matches = cv2.BFMatcher().knnMatch(da, db, k=2)
    matches = [m for m,n in matches if m.distance < .75 * n.distance]
    points_a = np.float32([ka[m.queryIdx].pt for m in matches])
    points_b = np.float32([kb[m.trainIdx].pt for m in matches])
    matrix, inlier = cv2.findHomography(points_a, points_b, cv2.RANSAC,
                                      config['alignment']['ransac_threshold_px'], maxIters=10000, confidence=.999)
    assert matrix is not None
    good = inlier.ravel().astype(bool)
    mapped = cv2.perspectiveTransform(points_a.reshape(1,-1,2), matrix).reshape(-1,2)
    errors = np.linalg.norm(mapped - points_b, axis=1)
    valid = int(good.sum()) >= config['alignment']['minimum_inliers'] and np.median(errors[good]) < 1
    return matrix, dict(method='surface_SIFT_RANSAC_homography', valid=bool(valid),
        after_to_before_homography=matrix.tolist(), matches=len(matches), inliers=int(good.sum()),
        inlier_median_reprojection_error_px=float(np.median(errors[good])),
        inlier_max_reprojection_error_px=float(np.max(errors[good])),
        inlier_hull_area_before_px=float(cv2.contourArea(cv2.convexHull(points_b[good]))),
        points_before=points_b.tolist(), points_after=points_a.tolist(), inlier=good.tolist(),
        stable_feature_mask_definition='P2 initial: only x104:179,y15:123 and x310:365,y10:115 immutable label bands. HOME/end: bounded front-plate polygon with x223:332,y28:149 excluded. No underlying lower plate, stain, tool or reflection features.',
        resampling='RGB bilinear for display; binary masks nearest-neighbor to initial reference grid',
        patch_checks=patch_checks)
