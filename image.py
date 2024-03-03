from typing import List, Tuple, Optional, Mapping, Dict
import os
import sys
from PIL import Image, ImageDraw
import numpy as np
import random
import cv2
import traceback
import statistics
import math
import csv
import pygame

# Input: a source image and perspective transform
# Output: a warped image and 2 translation terms
def perspective_warp(image: np.ndarray, transform: np.ndarray) -> Tuple[np.ndarray, int, int]:
    h, w = image.shape[:2]
    corners_bef = np.float32([[0, 0], [w, 0], [w, h], [0, h]]).reshape(-1, 1, 2)
    corners_aft = cv2.perspectiveTransform(corners_bef, transform)
    xmin = math.floor(corners_aft[:, 0, 0].min())
    ymin = math.floor(corners_aft[:, 0, 1].min())
    xmax = math.ceil(corners_aft[:, 0, 0].max())
    ymax = math.ceil(corners_aft[:, 0, 1].max())
    x_adj = math.floor(xmin - corners_aft[0, 0, 0])
    y_adj = math.floor(ymin - corners_aft[0, 0, 1])
    translate = np.eye(3)
    translate[0, 2] = -xmin
    translate[1, 2] = -ymin
    corrected_transform = np.matmul(translate, transform)
    return cv2.warpPerspective(image, corrected_transform, (math.ceil(xmax - xmin), math.ceil(ymax - ymin))), x_adj, y_adj

# Just like perspective_warp, but it also returns an alpha mask that can be used for blitting
def perspective_warp_with_mask(image: np.ndarray, transform: np.ndarray) -> Tuple[np.ndarray, np.ndarray, int, int]:
    mask_in = np.empty(image.shape, dtype = np.uint8)
    mask_in.fill(255)
    output, x_adj, y_adj = perspective_warp(image, transform)
    mask, _, _ = perspective_warp(mask_in, transform)
    return output, mask, x_adj, y_adj

# alpha_blits a 4-channel image onto a 3-channel image
def blit4(dest: np.ndarray, src: np.ndarray, x: int, y: int) -> None:
    dl = max(x, 0)
    dt = max(y, 0)
    sl = max(-x, 0)
    st = max(-y, 0)
    sr = max(sl, min(src.shape[1], dest.shape[1] - x))
    sb = max(st, min(src.shape[0], dest.shape[0] - y))
    dr = dl + sr - sl
    db = dt + sb - st
    m = src[st:sb, sl:sr, 3:4]
    dest[dt:db, dl:dr] = (dest[dt:db, dl:dr].astype(np.float64) * (255 - m) + src[st:sb, sl:sr, 0:3].astype(np.float64) * m) / 255

# alpha_blits src onto dest according to the alpha values in mask at location (x, y),
# ignoring any parts that do not overlap
def alpha_blit(dest: np.ndarray, src: np.ndarray, mask: np.ndarray, x: int, y: int) -> None:
    dl = max(x, 0)
    dt = max(y, 0)
    sl = max(-x, 0)
    st = max(-y, 0)
    sr = max(sl, min(src.shape[1], dest.shape[1] - x))
    sb = max(st, min(src.shape[0], dest.shape[0] - y))
    dr = dl + sr - sl
    db = dt + sb - st
    m = mask[st:sb, sl:sr]
    dest[dt:db, dl:dr] = (dest[dt:db, dl:dr].astype(np.float64) * (255 - m) + src[st:sb, sl:sr].astype(np.float64) * m) / 255

# blits a perspective-warped src image onto dest
def perspective_blit(dest: np.ndarray, src: np.ndarray, transform: np.ndarray) -> None:
    blitme, mask, x_adj, y_adj = perspective_warp_with_mask(src, transform)
    alpha_blit(dest, blitme, mask, int(transform[0, 2] + x_adj), int(transform[1, 2] + y_adj))

# blits a 4-channel perspective-warped src image onto a 3-channel dest
def perspective_blit4(dest: np.ndarray, src: np.ndarray, transform: np.ndarray) -> None:
    blitme, x_adj, y_adj = perspective_warp(src, transform)
    blit4(dest, blitme, int(transform[0, 2] + x_adj), int(transform[1, 2] + y_adj))


# Returns (m, b), such that y is approximately equal to np.matmul(x, m) + b.
def affine_regression(x: np.array, y: np.array) -> Tuple[np.array, np.array]:
    # Check assumptions
    assert x.shape[0] == y.shape[0]
    assert x.shape[1] > 0 and y.shape[1] > 0

    # Use OLS to compute reasonable starting weights
    x_mean = np.mean(x, axis = 0)
    y_mean = np.mean(y, axis = 0)
    x_centered = x - x_mean
    y_centered = y - y_mean
    num = np.matmul(np.transpose(y_centered), x_centered)
    den = np.matmul(np.transpose(x_centered), x_centered)
    m = np.transpose(np.matmul(num, np.linalg.pinv(den)))
    b = y_mean - np.matmul(x_mean, m)

    # Refine with gradient descent
    err = y - (np.matmul(x, m) + b)
    sse = np.sum(err * err)
    step = 0.01
    for i in range(16):
        grad_m = np.matmul(np.transpose(x), err)
        grad_b = np.sum(err, axis = 0)
        refined_m = m + step * grad_m
        refined_b = b + step * grad_b
        refined_err = y - (np.matmul(x, refined_m) + refined_b)
        refined_sse = np.sum(refined_err * refined_err)
        if refined_sse < sse:
            m = refined_m
            b = refined_b
            err = refined_err
            sse = refined_sse
        else:
            step *= 0.4
    return m, b

def test_affine_regression() -> None:
    x = np.array([[71.97040455],[340.56272532],[41.04888586],[1212.09793227]])
    y = np.array([[374.02851611],[379.28140507],[469.65706835],[391.04999145]])
    m, b = affine_regression(x, y)
    if abs(b - 414) > 10:
        raise ValueError('failed')
    if abs(m + 0.025) > 0.01:
        raise ValueError('failed')


# Adjusts the lighting of the input image. b, g, and r should be values centered at 0.
def adjust_lighting(image: np.ndarray, b: float, g: float, r: float) -> np.ndarray:
    lut_b = np.expand_dims(np.clip(np.power(np.arange(256) / 255.0, math.exp(b)) * 255.0, 0, 255).astype('uint8'), 1)
    lut_g = np.expand_dims(np.clip(np.power(np.arange(256) / 255.0, math.exp(g)) * 255.0, 0, 255).astype('uint8'), 1)
    lut_r = np.expand_dims(np.clip(np.power(np.arange(256) / 255.0, math.exp(r)) * 255.0, 0, 255).astype('uint8'), 1)
    lut = np.concatenate([lut_b, lut_g, lut_r], axis = 1).reshape([256, 1, 3])
    return cv2.LUT(image, lut)

def to_pygame_surface(image: np.ndarray) -> pygame.Surface:
    return pygame.surfarray.make_surface(cv2.cvtColor(np.transpose(image, axes=(1, 0, 2)), cv2.COLOR_BGR2RGB))

def scale_pg_image(image: pygame.image, scale: float) -> pygame.image:
    r = image.get_rect()
    new_size = (int(r[2] * scale), int(r[3] * scale))
    return pygame.transform.scale(image, new_size)
