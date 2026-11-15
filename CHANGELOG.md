# Changelog

## Unreleased – 15.11.2026

### Training and history

- Added Adam alongside SGD with Momentum. Training history stores the optimizer state for resuming compatible runs, and the mathematics view shows how Adam updates weights and biases.
- Added training with the same initialization so different settings can be compared from the same starting weights and biases. Changed settings can also start a linked continuation run.
- Added optional recording of two selected weights over the course of training. The 2D weight trajectory can be reviewed in the training window, compared across compatible runs in the history, and included in analysis and reports.
- Added a network characteristic preview for compatible saved runs. The history can also display linked continuation runs on a shared epoch axis.
- Added resizable live chart windows and a shared chart background setting. The training history gives more space to the plot and keeps the run table compact.
- Added a project-specific training protocol for changes to the network, data, scaling, and training parameters. The protocol can display run details in a table and apply saved parameters to the training dialog.
- Preserved incompatible history entries for documentation when training data, scaling, neuron assignments, or activations change, while preventing incompatible runs from being restored or continued.

### Network, data, and analysis

- Added interactive characteristic charts to the application view, with adjustable inputs, training points, and resizable chart windows. Improved the distinction between stored targets, interpolated targets, and predictions in the analysis view.
- Added a preview for automatic training-data scaling, including editable bounds, and a field for recording the origin of the training data.
- Added percentage deviations relative to the target or to the calibrated output range where applicable.
- Added progress feedback when opening projects and validation that rejects invalid network topology before loading it into the editor.
- Added display options to show, hide, or bundle network connections. Lowered the minimum zoom in the network overview from 20% to 10%.

### Project reports and HTML exports

- Redesigned HTML, PDF, and Word project reports with clearer sections, light-blue panels, and side-by-side charts where space permits. The HTML report places the full-width network diagram below the network summary.
- Added data origin, training-run details, weight trajectories, and classification results where available. Classification reports show how many cases the network classified correctly.
- Added separate public and author Windows builds. The build script lets the user choose the edition and writes either edition to the usual `dist/NeuronNet.exe` path. HTML exports are available in the author build.
- Added author HTML exports for project reports, training data tables, and the interactive Explore view. Training-data exports default to the project's training-data folder, and suggested filenames use hyphens in place of spaces.
- Added support for matrix controls and eligible network characteristics in Explore HTML. The characteristic slider stays aligned with the current point, and the transparent export can be embedded on a website.
- Added standalone HTML training clips for MSE, maximum individual error, recorded 2D weight trajectories, and network characteristics. The clip uses the chart and applicable scale selected in the training history, with configurable playback duration and end pause.
- Added colored labels and curve segments for linked runs. The clip displays the active run's training parameters alongside the results.
- Network-characteristic clips recompute the selected runs on a copy of the network at export time. A progress dialog shows the current run and epoch count and lets the user cancel before the file is written.
- Added an option to open the generated HTML in the browser after export.
- Aligned the headers of HTML training clips by removing the time-lapse and original-duration line.
- Added on-demand recomputation of missing 2D weight trajectories for HTML clips, with weight selection, progress, and cancellation.
- Use the same playback pace for all HTML training clips, with more time for the early epochs of each run.
- Renamed the application, exports, and Windows executable to NeuronNet. Existing settings and profiles remain compatible.

### Examples and documentation

- Updated the German and English example collections, including localized English project data and layouts.
- Updated the German and English integrated help and refreshed the packaged manuals. Added a web example for the three-zone temperature and process control project.

### Earlier unreleased changes

- Update the tested development runtime to Python 3.14.7 (64-bit), retaining PySide6 6.11.1 and PyInstaller 6.21.0. Document the environment in both README languages. The About dialog already reads the active Python runtime dynamically; existing executables retain their bundled runtime until rebuilt.

- Add optional automatic pruning to PLC exports (GX Works2, GX Works3 and IEC XML). The configurable absolute threshold defaults to 0.001; pruning is disabled by default. Omitted connections and weight constants affect only the export, and the preview shows the number removed. Nonzero thresholds may change model results.
- Confirm input/output structure changes before clearing training history; offer immediate training-data adjustment or cancellation. Preserve history for name-only changes. Add German and English warnings.

## 0.10.0-beta.07 – 10.10.2026

- improve speed during training

## 0.10.0-beta.06 – 02.10.2026

- add live network characteristic plots to the training and analysis views
- add zooming, panning, point details, dataset navigation, and comparison controls
- improve training rollback, error handling, chart rendering, and window layouts
- validate network connections and warn when connections skip layers
- extend graphical experiments with new controls, gauges, scalable layouts,standard symbols, and grouped logic symbols
- update translations, automated tests, example projects, and documentation
- refresh the German and English manuals and packaged tutorial files

## 0.10.0-beta.05 – 16.09.2026

- add profile storage

## 0.10.0-beta.04 – 05.09.2026

- Add error curve for maximum single error.

## 0.10.0-beta.03 – 03.09.2026

- add SPS export

## 0.10.0-beta.02 – 02.09.2026

- Added an optional experimental PLC Export menu.
- Added export support for Mitsubishi GX Works2 and GX Works3.
- Generated editable local-label declarations and Structured Text from trained networks.
- Added separate copy functions for declarations and ST code.
- Added GX Works2- and GX Works3-specific declaration layouts.
- Added Excel-compatible clipboard data for GX Works3.
- Added target-specific EXP syntax for GX Works2 and GX Works3.
- Added support for analog and binary inputs and outputs.
- Added scaling constants, trained weights, and bias values to the generated declarations.
- Added syntax highlighting and editable export content.
- Added placeholders for future CODESYS, TwinCAT, and Siemens SCL exporters.
- Added an Experimental settings page for showing or hiding the PLC Export menu.
- Updated the German and English integrated help.

## 0.10.0-beta.01 – 31.08.2026

- Added a comprehensive project health check covering the network, training data, calibration, training status, and analysis availability.
- Unified information dialogs across the application with consistent yellow information panels.
- Added context-sensitive information buttons to major working windows and analysis tabs.
- Improved the Application View with clearer information about Explore and Edit modes.
- Added a structured and scrollable calculation path for selected neurons.
- Added the unscaled output value to the calculation path of scaled analog output neurons.
- Added a permanent Elements menu to the Application View.
- Added interactive element placement with a movable preview, grid snapping, and cancellation using Esc or right-click.
- Improved clipboard handling for graphic shapes, comments, and background images.
- Added Copy commands to the context menus of copyable elements and Paste to the context menu of an empty canvas area.
- Moved the canvas background color command to the Design menu.
- Disabled and greyed out all editing menus in Explore mode.
- Improved multi-selection performance by no longer selecting adjacent network connections automatically.
- Improved line endpoint handling when moving multiple selected elements.
- Updated the German and English help documentation and marked outdated screenshots for replacement.

## 0.9.0-beta.15 – 15.08.2026

- Application View and Training Improvements

## 0.9.0-beta.14 – 08.08.2026

- Improve graphical experiment editor and usability

## 0.9.0-beta.13 – 06.08.2026

- add grafic experiment

## 0.9.0-beta.12 – 05.08.2026

- network Improvements, Training Window Improvements, Bugfixes

## 0.9.0-beta.11 – 04.08.2026

- Improvements TEst and Analysis Windows, bug fixes

## 0.9.0-beta.10 – 02.08.2026

- Improvements and bug fixes

## 0.9.0-beta.9 – 01.08.2026

- create english version projects

## 0.9.0-beta.8 – 01.08.2026

- Fixing minor bugs; creating an intro window

## 0.9.0-beta.7 – 31.07.2026

- general improvement of the training window

## 0.9.0-beta.6 – 31.07.2026

- KI Assistant integration
- Designed the training target and training controls as aligned groups with
  unambiguous option buttons, clearer labels, and additional help texts
- Combined the evaluation functions in a single-row toolbar and renamed the
  previous loading command to "Training History"
- Expanded the introductory text of the Project Assistant to explain its
  purpose and expected results
- Prevented unwanted separate error-message windows when returning from the
  compact or minimized view to the full view
- Added a calm, optional splash screen with a NeuronNet graphic, tagline,
  version information, and actual loading messages; centered it over the saved
  main-window position and kept it visible for 2.5 seconds after loading
- Preserved the last saved network view when a startup project is opened
  automatically
- Prevented temporary messages and the permanent project summary from
  overlapping in the status bar
- Extended "File → New" with a common selection for an empty project,
  automatic network generation, creation from training data, and the Project
  Assistant

## 0.9.0-beta.5 – 29.07.2026

- Improve training guidance, history curves, and project usability
- Revised the project report with formatted descriptions, a clearer header, a
  combined training table and curve, and complete output evaluations
- Added a project-independent assistant for generating editable AI prompts for
  custom projects, network proposals, and training data
- Updated the project prompt to request unscaled raw data; added access to the
  experiment from the training window and corrected the initial save location
  for new projects

## 0.9.0-beta.4 – 28.07.2026

- Improve training workflow, history and error display

## 0.9.0-beta.3 – 27.07.2026

- Analysis window revised
- Revised the training window with a common target selection for new and
  continued runs
- Allowed stopped training runs to continue with the same training target
- Extended the training history with the maximum individual error and an
  appropriate initial width
- Made automatic network arrangement initially retain the existing spacing
- Improved the layout of the influence analysis and technical training data
- Prevented the project overview from opening automatically at program startup
- Removed the unnecessary "Show Project Workflow" switch from the menu

## 0.9.0-beta.2 – 26.07.2026

- Version control established

## 0.9.0-beta.1 – 26.07.2026

- First centrally versioned public beta release of NeuronNet.
