# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [3.0.0] - 2026-06-16

### Added

- Camera toolbar action for exporting `BaseFigureWidget` charts as PNG files.

### Changed

- Moved figure toolbar and plot-shell Qt styling into the packaged
  `widgets.qss` stylesheet.
- Applied pyqtgraph-specific plot, axis, and legend styling during
  `BaseFigureWidget` initialization.

### Removed

- Removed the public `BaseFigureWidget.set_theme()` placeholder method.

## [2.0.0] - 2026-06-16

### Removed

- Removed the `pyqt_widget_kit.settings` package, its dedicated stylesheet,
  settings-window documentation, and settings-window demo.

## [1.1.0] - 2026-06-12

### Added

- Initial package metadata for `pyqt-widget-kit`.
- Reusable PyQt6 widgets including buttons, combo boxes, line edits, sliders,
  file inputs, list widgets, pill selectors, settings windows, and graph
  helpers.
- Bundled icons and optional QSS stylesheets.
- Settings-window documentation and runnable examples.
- `FigureSettings` typing for `BaseFigureWidget` visual settings.
- `BaseFigureWidget.apply_settings()` for typed, coercion-aware plot settings.
- `ScatterFigureWidget` for interactive scatter plots with per-point metadata,
  click signals, highlights, and rectangular selection.
- Scatter figure demo and focused scatter widget tests.
- GitHub release-note configuration for grouped release announcements.
- Tag-driven GitHub Actions release workflow for `vX.Y.Z` versions.
- README guidance for release notifications, changelog usage, and SemVer.

### Fixed

- GitHub Actions test workflow now installs Qt runtime libraries required for
  PyQt6 imports on Ubuntu runners.

[Unreleased]: https://github.com/anthony-bouh/pyqt-widget-kit/compare/v3.0.0...HEAD
[3.0.0]: https://github.com/anthony-bouh/pyqt-widget-kit/releases/tag/v3.0.0
[2.0.0]: https://github.com/anthony-bouh/pyqt-widget-kit/releases/tag/v2.0.0
[1.1.0]: https://github.com/anthony-bouh/pyqt-widget-kit/releases/tag/v1.1.0
