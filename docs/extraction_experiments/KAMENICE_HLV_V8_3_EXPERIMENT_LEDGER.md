# Kamenice HLV V8.3 Experiment Ledger

## Baseline Revalidation

- Raw fragment count: `56642`
- Merged polygon count: `1265`
- Geometry error count: `840`
- Export blocked count: `1265`
- Manual split required count: `875`
- Hatch candidate count: `635`
- Dotted boundary candidate count: `83`
- Thick boundary candidate count: `9`
- FID status: `{'329': 'found', '337': 'found', '353': 'found'}`

## First-Principles Decomposition

- Object: a planning-semantic polygon, not merely a same-fill-color region.
- Visual evidence: fill color, hatch/grid style, dotted/thick boundaries, text anchors, legend mapping, draw order, raster evidence, and manual correction.
- Vector evidence: fills, black dots, thick linework, text anchors, legend symbol/style records, draw order.
- Raster-only evidence: visual hatch/grid envelope when the PDF does not expose hatch as clean standalone vector strokes.
- Evidence lost after merge: tiny hatch/grid interior line/void structure can collapse into holes inside a merged same-fill polygon.
- Split-capable evidence: closed or near-closed hatch envelope, dotted boundary, thick boundary, and manual split geometry.
- Validate-only evidence: text anchors and legend mapping can classify/rank/reject but cannot create geometry alone.
- Human trust requires preserved raw geometry, visible evidence references, review-only candidates, and explicit export blocking until approved.

Required conclusion: fill color creates candidates; hatch/grid and dotted/thick boundaries define possible semantic subregions; text and legend validate; raster supports but cannot silently replace vector truth; manual split remains required when evidence is incomplete.

## Target Case

- Target: `Kamenice BX.p Z.51a hatch/dotted split`
- ROI: `[1222.64, 1364.2, 2014.2, 2046.44]`
- Current bad FIDs: `[329, 337, 353]`
- Target labels in ROI: `[{'text': 'Z.48', 'normalized': 'Z.48', 'bbox': [1774.24, 1398.066, 1805.935, 1413.906]}, {'text': 'Z.46', 'normalized': 'Z.46', 'bbox': [1787.92, 1506.306, 1819.615, 1522.146]}, {'text': 'Z.43a', 'normalized': 'Z.43a', 'bbox': [1540.48, 1705.506, 1580.982, 1721.346]}, {'text': 'Z.42', 'normalized': 'Z.42', 'bbox': [1453.72, 1630.986, 1485.415, 1646.826]}, {'text': 'Z.41', 'normalized': 'Z.41', 'bbox': [1398.64, 1700.54, 1422.411, 1712.42]}, {'text': 'Z.40d', 'normalized': 'Z.40d', 'bbox': [1313.44, 1856.466, 1354.813, 1872.306]}, {'text': 'Z.40a', 'normalized': 'Z.40a', 'bbox': [1602.16, 1846.626, 1642.662, 1862.466]}, {'text': 'Z.51a', 'normalized': 'Z.51a', 'bbox': [1800.76, 1769.946, 1841.262, 1785.786]}, {'text': 'Z.53', 'normalized': 'Z.53', 'bbox': [1916.44, 1914.906, 1948.135, 1930.746]}, {'text': 'Z.44b', 'normalized': 'Z.44b', 'bbox': [1606.48, 1679.586, 1647.853, 1695.426]}, {'text': 'Z.3-7', 'normalized': 'Z.3', 'bbox': [1773.865, 1639.768, 1801.479, 1668.136]}, {'text': 'Z.45', 'normalized': 'Z.45', 'bbox': [1658.44, 1669.266, 1690.135, 1685.106]}, {'text': 'Z.47', 'normalized': 'Z.47', 'bbox': [1715.08, 1617.906, 1746.775, 1633.746]}, {'text': 'Z.46', 'normalized': 'Z.46', 'bbox': [1700.44, 1570.026, 1732.135, 1585.866]}, {'text': 'Z.48', 'normalized': 'Z.48', 'bbox': [1833.4, 1427.586, 1865.095, 1443.426]}, {'text': 'Z.53', 'normalized': 'Z.53', 'bbox': [1809.28, 1522.986, 1840.975, 1538.826]}, {'text': 'BX.c', 'normalized': 'BX.c', 'bbox': [1891.678, 1870.145, 1912.859, 1879.768]}, {'text': 'BX.c', 'normalized': 'BX.c', 'bbox': [1826.638, 1389.785, 1847.819, 1399.408]}, {'text': 'BX.c', 'normalized': 'BX.c', 'bbox': [1811.158, 1428.304, 1832.339, 1437.928]}, {'text': 'BX.c', 'normalized': 'BX.c', 'bbox': [1829.158, 1485.665, 1850.339, 1495.288]}, {'text': 'BX.c', 'normalized': 'BX.c', 'bbox': [1419.838, 1514.584, 1441.019, 1524.208]}, {'text': 'BX.c', 'normalized': 'BX.c', 'bbox': [1379.956, 1662.183, 1401.19, 1671.928]}, {'text': 'BX.c', 'normalized': 'BX.c', 'bbox': [1508.758, 1711.025, 1529.939, 1720.648]}, {'text': 'BX.c', 'normalized': 'BX.c', 'bbox': [1446.598, 1729.745, 1467.779, 1739.368]}, {'text': 'BX.c', 'normalized': 'BX.c', 'bbox': [1386.676, 1747.263, 1407.91, 1757.008]}, {'text': 'BX.c', 'normalized': 'BX.c', 'bbox': [1574.158, 1798.145, 1595.339, 1807.768]}, {'text': 'BX.c', 'normalized': 'BX.c', 'bbox': [1644.598, 1742.944, 1665.779, 1752.568]}, {'text': 'BX.c', 'normalized': 'BX.c', 'bbox': [1705.318, 1784.224, 1726.499, 1793.848]}, {'text': 'BX.c', 'normalized': 'BX.c', 'bbox': [1720.918, 1738.385, 1742.099, 1748.008]}, {'text': 'BX.c', 'normalized': 'BX.c', 'bbox': [1752.838, 1761.905, 1774.019, 1771.528]}, {'text': 'BX.c', 'normalized': 'BX.c', 'bbox': [1830.238, 1597.984, 1851.419, 1607.608]}, {'text': 'BX.c', 'normalized': 'BX.c', 'bbox': [1811.518, 1612.265, 1832.699, 1621.888]}, {'text': 'BX.c', 'normalized': 'BX.c', 'bbox': [1930.636, 1745.943, 1951.87, 1755.688]}, {'text': 'BX.c', 'normalized': 'BX.c', 'bbox': [1900.678, 1774.505, 1921.859, 1784.128]}, {'text': 'BX.c', 'normalized': 'BX.c', 'bbox': [1865.596, 1791.303, 1886.83, 1801.048]}, {'text': 'BX.c', 'normalized': 'BX.c', 'bbox': [1842.238, 1842.304, 1863.419, 1851.928]}, {'text': 'BX.c', 'normalized': 'BX.c', 'bbox': [1834.678, 1929.184, 1855.859, 1938.808]}, {'text': 'BX.c', 'normalized': 'BX.c', 'bbox': [1702.918, 1980.904, 1724.099, 1990.528]}, {'text': 'BX.c', 'normalized': 'BX.c', 'bbox': [1614.478, 1897.025, 1635.659, 1906.648]}, {'text': 'BX.c', 'normalized': 'BX.c', 'bbox': [1609.918, 1917.304, 1631.099, 1926.928]}, {'text': 'BX.c', 'normalized': 'BX.c', 'bbox': [1619.638, 1938.785, 1640.819, 1948.408]}, {'text': 'BX.c', 'normalized': 'BX.c', 'bbox': [1489.876, 1813.983, 1511.11, 1823.728]}, {'text': 'BX.c', 'normalized': 'BX.c', 'bbox': [1316.356, 1870.623, 1337.59, 1880.368]}, {'text': 'BX.c', 'normalized': 'BX.c', 'bbox': [1405.078, 1838.704, 1426.259, 1848.328]}, {'text': 'BX.p', 'normalized': 'BX.p', 'bbox': [1740.239, 1529.584, 1761.941, 1539.208]}, {'text': 'BX.p', 'normalized': 'BX.p', 'bbox': [1772.879, 1713.424, 1794.581, 1723.048]}, {'text': 'BX.p', 'normalized': 'BX.p', 'bbox': [1622.718, 1598.943, 1644.472, 1608.688]}, {'text': 'BX.p', 'normalized': 'BX.p', 'bbox': [1760.279, 1442.584, 1781.981, 1452.208]}, {'text': 'BX.p', 'normalized': 'BX.p', 'bbox': [1741.079, 1713.904, 1762.781, 1723.528]}, {'text': 'BX.p', 'normalized': 'BX.p', 'bbox': [1802.639, 1462.264, 1824.341, 1471.888]}, {'text': 'BX.c', 'normalized': 'BX.c', 'bbox': [1835.158, 1419.545, 1856.339, 1429.168]}, {'text': 'BX.c', 'normalized': 'BX.c', 'bbox': [1777.918, 1376.824, 1799.099, 1386.448]}, {'text': 'BX.c', 'normalized': 'BX.c', 'bbox': [1460.638, 1648.505, 1481.819, 1658.128]}, {'text': 'BX.c', 'normalized': 'BX.c', 'bbox': [1366.198, 1681.265, 1387.379, 1690.888]}, {'text': 'BX.c', 'normalized': 'BX.c', 'bbox': [1570.678, 1835.464, 1591.859, 1845.088]}, {'text': 'BX.c', 'normalized': 'BX.c', 'bbox': [1659.358, 1684.385, 1680.539, 1694.008]}, {'text': 'BX.c', 'normalized': 'BX.c', 'bbox': [1526.956, 1870.143, 1548.19, 1879.888]}, {'text': 'BX.c', 'normalized': 'BX.c', 'bbox': [1310.836, 1838.703, 1332.07, 1848.448]}, {'text': 'BX.c', 'normalized': 'BX.c', 'bbox': [1914.718, 1907.704, 1935.899, 1917.328]}, {'text': 'BX.p', 'normalized': 'BX.p', 'bbox': [1710.719, 1515.304, 1732.421, 1524.928]}, {'text': 'BX.p', 'normalized': 'BX.p', 'bbox': [1739.959, 1611.906, 1761.712, 1621.648]}, {'text': 'BX.p', 'normalized': 'BX.p', 'bbox': [1815.839, 1508.704, 1837.541, 1518.328]}, {'text': 'BX.p', 'normalized': 'BX.p', 'bbox': [1814.279, 1753.864, 1835.981, 1763.488]}, {'text': 'BX.p', 'normalized': 'BX.p', 'bbox': [1816.559, 1538.584, 1838.261, 1548.208]}, {'text': 'BX.c', 'normalized': 'BX.c', 'bbox': [1849.798, 1373.284, 1863.936, 1379.739]}, {'text': 'BX.p', 'normalized': 'BX.p', 'bbox': [1674.599, 1577.344, 1696.301, 1586.968]}, {'text': 'BX.c', 'normalized': 'BX.c', 'bbox': [1669.078, 1649.224, 1690.259, 1658.848]}, {'text': 'BX.c', 'normalized': 'BX.c', 'bbox': [1950.436, 1892.703, 1971.67, 1902.448]}, {'text': 'BX.c', 'normalized': 'BX.c', 'bbox': [1537.558, 1727.344, 1558.739, 1736.968]}, {'text': 'BX.c', 'normalized': 'BX.c', 'bbox': [1599.958, 1703.344, 1621.139, 1712.968]}, {'text': 'BX.c', 'normalized': 'BX.c', 'bbox': [1575.238, 1686.665, 1596.419, 1696.288]}, {'text': 'BX.p', 'normalized': 'BX.p', 'bbox': [1608.918, 1643.943, 1630.672, 1653.688]}, {'text': 'BX.p', 'normalized': 'BX.p', 'bbox': [1633.919, 1660.864, 1655.621, 1670.488]}, {'text': 'Z.44a', 'normalized': 'Z.44a', 'bbox': [1613.08, 1645.626, 1653.582, 1661.466]}, {'text': 'Z.43b', 'normalized': 'Z.43b', 'bbox': [1589.56, 1712.706, 1630.933, 1728.546]}]`

## Raster Diagnostics

- E02 overlay: `/mnt/c/coding/up_layer_extractor/docs/extraction_experiments/kamenice_e02_raster_hatch_overlay.png`
- E02 hatch pixels: `25993`
- E03 overlay: `/mnt/c/coding/up_layer_extractor/docs/extraction_experiments/kamenice_e03_dotted_boundary_overlay.png`
- E03 dark pixels: `115840`

## Experiments

### E01 — vector_hatch_line_premerge_index

- Hypothesis: White hatch/grid lines can be isolated before polygon merging.
- First-principles rationale: evidence is evaluated by what can actually split geometry versus what can only validate it.
- Input evidence used: `{'white_thin_line_count': 281, 'parallel_groups': 0, 'grid_groups': 0, 'hatch_region_candidates': 0, 'target_roi_hatch_detected': False}`
- Algorithm sketch: run detector/scorer, emit review-only evidence, preserve raw and merged geometry.
- Implementation files: `backend/app/experiment_lab.py`, `scripts/run_kamenice_v8_3_experiments.py`
- Parameters/thresholds: near-white >=232/235; near-black <=45; hybrid score thresholds 0.85/0.65/0.40.
- Result: PDF drawing index did not expose target hatch as usable standalone white vector strokes.
- Metrics: `{'white_thin_line_count': 281, 'parallel_groups': 0, 'grid_groups': 0, 'hatch_region_candidates': 0, 'target_roi_hatch_detected': False}`
- Screenshots/diagnostics produced: `[]`
- Failure reason, if failed: see result summary
- What was learned: The Kamenice hatch signal is mostly preserved as post-merge hatch-grid hole artifacts, so vector-only pre-merge hatch detection is insufficient.
- Next action: combine or keep according to row decision
- Keep / reject / combine: `reject`

### E02 — raster_hatch_grid_segmentation

- Hypothesis: Rendered page raster can reveal hatch/grid regions when vector strokes are not isolated.
- First-principles rationale: evidence is evaluated by what can actually split geometry versus what can only validate it.
- Input evidence used: `{'render_dpi': 144, 'white_grid_pixel_count': 25993, 'line_segments_detected': None, 'grid_orientation_count': 2, 'hatch_mask_area': 25993, 'hatch_envelope_polygon_count': 1, 'target_roi_hatch_detected': True, 'false_positive_risk': 'medium'}`
- Algorithm sketch: run detector/scorer, emit review-only evidence, preserve raw and merged geometry.
- Implementation files: `backend/app/experiment_lab.py`, `scripts/run_kamenice_v8_3_experiments.py`
- Parameters/thresholds: near-white >=232/235; near-black <=45; hybrid score thresholds 0.85/0.65/0.40.
- Result: Raster/merged-hole evidence confirms hatch/grid presence but does not independently define an exact exportable split.
- Metrics: `{'render_dpi': 144, 'white_grid_pixel_count': 25993, 'line_segments_detected': None, 'grid_orientation_count': 2, 'hatch_mask_area': 25993, 'hatch_envelope_polygon_count': 1, 'target_roi_hatch_detected': True, 'false_positive_risk': 'medium'}`
- Screenshots/diagnostics produced: `['docs/extraction_experiments/kamenice_e02_raster_hatch_overlay.png']`
- Failure reason, if failed: not failed
- What was learned: Raster evidence is useful for locating hatch envelopes and must be combined with boundary/text evidence.
- Next action: combine or keep according to row decision
- Keep / reject / combine: `combine`

### E03 — dotted_boundary_reconstruction

- Hypothesis: Black dots along the target region form a closed or near-closed split boundary.
- First-principles rationale: evidence is evaluated by what can actually split geometry versus what can only validate it.
- Input evidence used: `{'dot_candidates': 115840, 'chains': 1, 'closed_or_near_closed_chains': 0, 'boundary_polygon_candidates': 1, 'contains_target_label': True, 'target_roi_boundary_detected': True}`
- Algorithm sketch: run detector/scorer, emit review-only evidence, preserve raw and merged geometry.
- Implementation files: `backend/app/experiment_lab.py`, `scripts/run_kamenice_v8_3_experiments.py`
- Parameters/thresholds: near-white >=232/235; near-black <=45; hybrid score thresholds 0.85/0.65/0.40.
- Result: Dotted boundary candidates exist, but closure is not reliable enough for automatic export geometry.
- Metrics: `{'dot_candidates': 115840, 'chains': 1, 'closed_or_near_closed_chains': 0, 'boundary_polygon_candidates': 1, 'contains_target_label': True, 'target_roi_boundary_detected': True}`
- Screenshots/diagnostics produced: `['docs/extraction_experiments/kamenice_e03_dotted_boundary_overlay.png']`
- Failure reason, if failed: not failed
- What was learned: Dotted-boundary evidence should rank/shape review candidates, not silently cut final polygons.
- Next action: combine or keep according to row decision
- Keep / reject / combine: `combine`

### E04 — thick_boundary_segmentation

- Hypothesis: Thicker/darker linework defines semantic area boundaries.
- First-principles rationale: evidence is evaluated by what can actually split geometry versus what can only validate it.
- Input evidence used: `{'thick_line_candidates': 9, 'closed_boundary_candidates': 0, 'barrier_lines_used': 9, 'split_candidates_created': 0, 'target_roi_split_supported': True}`
- Algorithm sketch: run detector/scorer, emit review-only evidence, preserve raw and merged geometry.
- Implementation files: `backend/app/experiment_lab.py`, `scripts/run_kamenice_v8_3_experiments.py`
- Parameters/thresholds: near-white >=232/235; near-black <=45; hybrid score thresholds 0.85/0.65/0.40.
- Result: Thick dark boundaries support the split hypothesis but do not provide a complete closed split graph.
- Metrics: `{'thick_line_candidates': 9, 'closed_boundary_candidates': 0, 'barrier_lines_used': 9, 'split_candidates_created': 0, 'target_roi_split_supported': True}`
- Screenshots/diagnostics produced: `[]`
- Failure reason, if failed: not failed
- What was learned: Thick boundaries are barrier evidence for hybrid scoring, not standalone geometry.
- Next action: combine or keep according to row decision
- Keep / reject / combine: `combine`

### E05 — text_anchor_constrained_assignment

- Hypothesis: Text labels validate or assign split candidates but must not create geometry alone.
- First-principles rationale: evidence is evaluated by what can actually split geometry versus what can only validate it.
- Input evidence used: `{'text_anchors_detected': 270, 'target_labels_detected': ['Z.48', 'Z.46', 'Z.43a', 'Z.42', 'Z.41', 'Z.40d', 'Z.40a', 'Z.51a', 'Z.53', 'Z.44b', 'Z.3', 'Z.45', 'Z.47', 'Z.46', 'Z.48', 'Z.53', 'BX.c', 'BX.c', 'BX.c', 'BX.c', 'BX.c', 'BX.c', 'BX.c', 'BX.c', 'BX.c', 'BX.c', 'BX.c', 'BX.c', 'BX.c', 'BX.c', 'BX.c', 'BX.c', 'BX.c', 'BX.c', 'BX.c', 'BX.c', 'BX.c', 'BX.c', 'BX.c', 'BX.c', 'BX.c', 'BX.c', 'BX.c', 'BX.c', 'BX.p', 'BX.p', 'BX.p', 'BX.p', 'BX.p', 'BX.p', 'BX.c', 'BX.c', 'BX.c', 'BX.c', 'BX.c', 'BX.c', 'BX.c', 'BX.c', 'BX.c', 'BX.p', 'BX.p', 'BX.p', 'BX.p', 'BX.p', 'BX.c', 'BX.p', 'BX.c', 'BX.c', 'BX.c', 'BX.c', 'BX.c', 'BX.p', 'BX.p', 'Z.44a', 'Z.43b'], 'labels_inside_candidate': 75, 'labels_near_candidate': 0, 'conflicting_labels': 0}`
- Algorithm sketch: run detector/scorer, emit review-only evidence, preserve raw and merged geometry.
- Implementation files: `backend/app/experiment_lab.py`, `scripts/run_kamenice_v8_3_experiments.py`
- Parameters/thresholds: near-white >=232/235; near-black <=45; hybrid score thresholds 0.85/0.65/0.40.
- Result: Target labels are assignment/validation evidence only; they do not split same-fill geometry by themselves.
- Metrics: `{'text_anchors_detected': 270, 'target_labels_detected': ['Z.48', 'Z.46', 'Z.43a', 'Z.42', 'Z.41', 'Z.40d', 'Z.40a', 'Z.51a', 'Z.53', 'Z.44b', 'Z.3', 'Z.45', 'Z.47', 'Z.46', 'Z.48', 'Z.53', 'BX.c', 'BX.c', 'BX.c', 'BX.c', 'BX.c', 'BX.c', 'BX.c', 'BX.c', 'BX.c', 'BX.c', 'BX.c', 'BX.c', 'BX.c', 'BX.c', 'BX.c', 'BX.c', 'BX.c', 'BX.c', 'BX.c', 'BX.c', 'BX.c', 'BX.c', 'BX.c', 'BX.c', 'BX.c', 'BX.c', 'BX.c', 'BX.c', 'BX.p', 'BX.p', 'BX.p', 'BX.p', 'BX.p', 'BX.p', 'BX.c', 'BX.c', 'BX.c', 'BX.c', 'BX.c', 'BX.c', 'BX.c', 'BX.c', 'BX.c', 'BX.p', 'BX.p', 'BX.p', 'BX.p', 'BX.p', 'BX.c', 'BX.p', 'BX.c', 'BX.c', 'BX.c', 'BX.c', 'BX.c', 'BX.p', 'BX.p', 'Z.44a', 'Z.43b'], 'labels_inside_candidate': 75, 'labels_near_candidate': 0, 'conflicting_labels': 0}`
- Screenshots/diagnostics produced: `[]`
- Failure reason, if failed: not failed
- What was learned: Text anchors are kept as constraints for E06 and manual split payloads.
- Next action: combine or keep according to row decision
- Keep / reject / combine: `combine`

### E06 — hybrid_graph_constrained_polygonization

- Hypothesis: Combine fill, hatch, boundary, text, and legend evidence in a review-only graph.
- First-principles rationale: evidence is evaluated by what can actually split geometry versus what can only validate it.
- Input evidence used: `{'candidate_regions': 1, 'candidate_score_best': 0.8, 'selected_candidate_has_hatch': True, 'selected_candidate_has_boundary': True, 'selected_candidate_has_text_anchor': True, 'manual_review_required': True}`
- Algorithm sketch: run detector/scorer, emit review-only evidence, preserve raw and merged geometry.
- Implementation files: `backend/app/experiment_lab.py`, `scripts/run_kamenice_v8_3_experiments.py`
- Parameters/thresholds: near-white >=232/235; near-black <=45; hybrid score thresholds 0.85/0.65/0.40.
- Result: Hybrid graph can produce a review-only ROI candidate, but confidence is not high enough for clean export.
- Metrics: `{'candidate_regions': 1, 'candidate_score_best': 0.8, 'selected_candidate_has_hatch': True, 'selected_candidate_has_boundary': True, 'selected_candidate_has_text_anchor': True, 'manual_review_required': True}`
- Screenshots/diagnostics produced: `[]`
- Failure reason, if failed: not failed
- What was learned: The best current method is evidence-combined review candidate generation with export blocked.
- Next action: operator reviews ROI candidate and records manual_semantic_split child geometries if accepted
- Keep / reject / combine: `combine`

### E07 — manual_split_fallback_schema

- Hypothesis: Ambiguous UP PDFs need first-class manual semantic split payloads.
- First-principles rationale: evidence is evaluated by what can actually split geometry versus what can only validate it.
- Input evidence used: `{'fallback_payloads': 1, 'raw_preserved': True, 'export_blocked': True}`
- Algorithm sketch: run detector/scorer, emit review-only evidence, preserve raw and merged geometry.
- Implementation files: `backend/app/experiment_lab.py`, `scripts/run_kamenice_v8_3_experiments.py`
- Parameters/thresholds: near-white >=232/235; near-black <=45; hybrid score thresholds 0.85/0.65/0.40.
- Result: Manual split schema is available and linked to the target ROI evidence.
- Metrics: `{'fallback_payloads': 1, 'raw_preserved': True, 'export_blocked': True}`
- Screenshots/diagnostics produced: `[]`
- Failure reason, if failed: not failed
- What was learned: Manual split remains the safe operational fallback for Kamenice.
- Next action: combine or keep according to row decision
- Keep / reject / combine: `keep`

### E08 — synthetic_controls_and_regression_tests

- Hypothesis: Synthetic controls isolate each signal detector and prevent future Kamenice-only overfitting.
- First-principles rationale: evidence is evaluated by what can actually split geometry versus what can only validate it.
- Input evidence used: `{'synthetic_hatch_detected': True, 'synthetic_dotted_boundary_detected': True, 'synthetic_thick_boundary_detected': True, 'text_anchor_assigns_without_split': True, 'label_mask_candidate_cleaned': True, 'real_void_preserved': True}`
- Algorithm sketch: run detector/scorer, emit review-only evidence, preserve raw and merged geometry.
- Implementation files: `backend/app/experiment_lab.py`, `scripts/run_kamenice_v8_3_experiments.py`
- Parameters/thresholds: near-white >=232/235; near-black <=45; hybrid score thresholds 0.85/0.65/0.40.
- Result: Synthetic fixtures cover hatch, dotted, thick, text, label-mask, and real-void behavior.
- Metrics: `{'synthetic_hatch_detected': True, 'synthetic_dotted_boundary_detected': True, 'synthetic_thick_boundary_detected': True, 'text_anchor_assigns_without_split': True, 'label_mask_candidate_cleaned': True, 'real_void_preserved': True}`
- Screenshots/diagnostics produced: `[]`
- Failure reason, if failed: not failed
- What was learned: Keep synthetic controls as regression guardrails while Kamenice remains review-blocked.
- Next action: combine or keep according to row decision
- Keep / reject / combine: `keep`

## Current Decision

- Best current method: `E06 hybrid graph review-only candidate + E07 manual split fallback`
- Resolved: `False`
- Remaining blockers: `['dotted/thick boundary graph is not closed enough for automatic export geometry', 'raster hatch envelope supports review but cannot replace vector truth', 'text anchors validate candidate semantics but cannot split geometry alone']`
- Next required step: `operator reviews ROI candidate and records manual_semantic_split child geometries if accepted`
