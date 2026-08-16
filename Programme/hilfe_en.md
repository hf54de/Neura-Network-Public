# NeuronNetz – Help and User Guide

This integrated help explains the principal workflows, windows, and controls directly in the program. The illustrated Word or PDF manual can additionally be opened through **Help → Tutorials**.

---

# 1. Overview

**NeuronNetz** is a graphical editor for creating, training, and examining small neural networks. Neurons, connections, weights, activation functions, and calculation values remain visible and can be edited deliberately.

A typical workflow is:

1. Create or open a project.
2. Build the network.
3. Enter, import, and scale training data.
4. Assign columns to input and output neurons.
5. Validate and train the network.
6. Test, analyze, or experiment with the result.
7. Save the project.

# 2. Program Interface

The **canvas** shows neurons, connections, and comments. The **Properties** panel on the right edits the selected object and shows its current calculation path under **Mathematics**.

Menus and toolbars provide the same functions. The status bar reports project state, data assignment, training results, and zoom.

Important menus:

- **File:** new project, open, save, description, and report.
- **Edit:** undo, redo, copy, paste, and delete.
- **View:** display options and zoom.
- **Network:** create, arrange, validate, explore, train, and analyze.
- **Training Data:** manage training and test data.
- **Settings:** program settings and language.
- **Help:** integrated help, tutorials, and program information.

# 3. New Project

**File → New** opens the starting-point selection:

- **Create Empty Project:** begin completely manually.
- **Create Network Automatically:** specify layers and neuron counts.
- **Create Network from Training Data:** begin with table structure and data.
- **Develop Your Own Project Idea:** prepare an editable prompt for an external AI.

A following setup dialog can be cancelled without changing the current project. The project assistant never modifies the current project.

A new project uses default colors, display settings, and training parameters. General program settings remain unchanged.

# 4. Creating a Neuron

Create a neuron with **Network → Create Neuron** or the corresponding tool, then click the desired position on the canvas.

Use the Properties panel to set name, type, activation function, bias, and other values. Names should be short and unambiguous.

# 5. Neuron Types

- **Input:** accepts an input value. Input neurons have no bias and no separate activation function.
- **Hidden:** processes weighted inputs and forwards the result of its activation function.
- **Output:** calculates a network output and is compared with a target during training.

Binary external values use 0 and 1. Analog values should be scaled appropriately.

# 6. Neuron Properties

The **Object** tab contains name, type, activation function, bias, and position. Runtime values such as X, weighted sum Σ, and output Y are read-only.

The **Mathematics** tab breaks down the current forward calculation and, after a learning step, the backward calculation. Only quantities relevant to the selected input, hidden, or output neuron are shown.

# 7. Creating Connections

Select **Network → Create Connection**, click the source neuron, and then click the target neuron. Connections must follow the information flow, typically Input → Hidden → Output.

Loops, duplicate connections, and invalid directions are prevented or reported by network validation.

# 8. Connection Properties

A selected connection shows source, target, weight, and calculation path. Positive and negative weights can be distinguished by color and line width.

The weight determines how strongly and in which direction the source neuron's output affects the target neuron.

# 9. Comments

Comments label areas of the canvas and are saved with the project. Text, size, font size, color, and position can be changed in the Properties panel.

Comments do not affect network calculations.

# 10. Selecting and Moving Objects

- Click to select an object.
- **Ctrl+Click** adds or removes an object from the selection.
- Drag on an empty area to create a rectangle selection.
- Drag a selected neuron or comment to move the selection.
- Drag on an empty area to pan the view; **Alt+Drag** also enables hand mode.

# 11. Copy, Cut, and Paste

Neurons, internal connections, and comments can be copied, cut, and pasted. Pasted objects receive new IDs; external connections to objects that were not copied are not created.

The editor clipboard is project-internal. Validate the network again after structural changes.

# 12. Undo and Redo

**Ctrl+Z** undoes the last editor change; **Ctrl+Y** restores it. This includes creating, deleting, moving, pasting, and editing properties.

File operations and completed training runs are not part of the normal editor history.

# 13. View and Zoom

- **Larger / Smaller:** change zoom step by step.
- **100%:** restore standard zoom.
- **Show All:** fit all visible project objects into the available area.
- Mouse wheel: zoom.
- Drag an empty area or use **Alt+Drag:** pan the view.

Zoom and the visible center are saved with the project.

# 14. Program Settings

The **Display** and **Colors** pages contain project-specific settings. They are stored in the respective `.nnproj` file and restored when switching projects.

Project-specific settings include:

- visible weights, calculation values, names, ports, comments, and activation charts,
- weight visualization by color and line width,
- colors of neurons, connections, comments, and canvas.

Toolbars, Properties panel, project previews, project assistant, editor behavior, startup, project folder, and language are program-wide settings.

A new project starts with the fixed defaults for project-specific settings.

# 15. Creating a Network Automatically

Start with **File → New → Create Network Automatically**. Specify input neurons, hidden layers, hidden neurons, output neurons, and activation functions.

Optionally connect consecutive layers fully and create an empty training-data structure. Only **OK** creates the new project; **Cancel** leaves the current project unchanged.

Use **Network → Arrange** to rearrange an existing network without changing weights, biases, or connections.

# 16. Training Data

Open the table with **Training Data → Edit Training Data**. Each row is a record; each column belongs to an input or an output/target.

Data can be:

- entered directly,
- pasted as tab-separated values,
- imported from CSV,
- opened from an existing `.nndata` file.

Only numeric values are accepted. The number of pasted or imported columns must match the table structure; missing columns are not filled with zeros.

**Scale Automatically from Table Data** is enabled only when at least one complete numeric record exists.

# 17. Assigning and Scaling Training Data

Right-click a column header to open its properties directly. **Edit Column Headers** presents the editable header information for all columns in one table. Names, units, and binary/analog data types can therefore be reviewed without opening every column separately. The input/output role and assigned neuron are shown but are not changed accidentally.

Changing an analog column temporarily to binary does not discard its stored analog calibration. When it is changed back to analog, **Determine from Table Data** becomes available again.

Analog values outside −1 to +1 should be scaled. Unscaled values do not block training, but may make it slow, unstable, or unsuccessful. Yellow column headers indicate recommended scaling; binary 0/1 columns do not require it.

**Define Input Array** arranges binary inputs as a two-dimensional pattern. It is useful for recognizing digits, letters, or symbols and is enabled only when all inputs are binary.

# 18. Starting Training

Open training with **Network → Train with Training Data**. A valid network, complete data assignments, and at least one training record are required.

The training window shows project, record count, network structure, parameter count, result values, and error curve. Review warnings about unscaled data before starting.

# 19. Training Parameters

Weights and biases can be initialized before a new run. **Xavier/Glorot** for weights and **Bias = 0** are the recommended starting values.

- **Learning rate:** size of parameter changes.
- **Momentum:** portion of the preceding parameter change carried into the next learning step. `0` disables momentum; high values may accelerate learning but can also cause overshooting.
- **Error limit:** desired mean epoch error.
- **Maximum epochs:** safety limit for the run.
- **Suggest Settings:** create a conservative starting suggestion from network size, activation functions, and assigned training data. The suggestion can be applied or discarded and does not guarantee a successful run.
- **Monitor data:** update the network visibly during training. When cleared, the canvas remains frozen while result fields, epoch count, elapsed time, and the error curve continue to update. This avoids the additional graphical work and makes training faster. The canvas is refreshed when monitoring is enabled again or the training window is closed.
- **Error curve:** show or hide the curve.

Training targets are **1 Epoch**, a fixed **Count**, or **Until Error Limit**.

# 20. Controlling and Observing Training

- **Start New Training:** begin a new run with the selected initialization options.
- **New Training with Same Starting Conditions:** begin a separate run with the original weights, bias values, and training-record order of the displayed run. The currently selected learning rate, momentum, error limit, and maximum epoch count are used; momentum states start at zero. With unchanged parameters, the resulting curves are reproducible. The function is available only when compatible starting conditions have been stored for the current network structure.
- **Continue:** continue the same run with its weights, biases, momentum states, epoch count, and error curve. Learning rate and momentum must retain their original values.
- **Stop:** finish the current calculation step in a controlled way.
- **Explore:** inspect the current trained state interactively.
- **Test and Analyze:** evaluate training or test data.
- **Debug Training:** inspect one learning step in detail.
- **Training History:** compare or restore previous runs.

The error curve's Y axis can be linear or logarithmic. Full, compact, and minimized views change only the display, not the training state.

The minimized view leaves the canvas visible and acts as a small training controller. It shows the run number, current epoch, elapsed time, selected target, and the **Live** setting. It also contains **New**, **Continue**, **Stop**, **Full View**, and **Compact View**. These controls operate the same training run as the full window.

With the target **1 Epoch**, each click on **Continue** processes exactly one additional epoch. This is useful for observing changes on the canvas step by step. Enable **Live** when the network values should be refreshed after the step; disable it when maximum speed is more important.

# 21. Test and Analysis

The analysis window compares target and actual values for training data or separate test data. It contains:

- record comparison,
- error analysis,
- target/actual chart,
- tolerance check,
- influence analysis.

Test data must use the same column structure and assignment as training data. Testing does not change weights or biases.

# 22. Exploring the Network

The experiment window changes external input values in their original units and immediately performs a forward calculation.

Binary inputs are switched; analog inputs use number fields or sliders. **Show Intermediate Values** also refreshes calculations in the Properties panel. Analog outputs show their raw and internal values. For binary outputs, intermediate values can be displayed in addition to the interpreted 0/1 decision.

The colored support indicator estimates whether the current input combination is well represented by similar training records. It is not a target value and is not proof that an output is correct. Experimenting does not change weights or the saved training state.

# 23. Application View

The application view presents the inputs and outputs of a trained network in a freely designed control panel. Results therefore do not have to be assessed from numbers alone. Input values can be changed directly, while indicators, switches, and gauges make the network's response immediately visible. Background images and labels connect the network to a practical application.

The function is available when a valid network exists, training data are assigned, and all input and output columns are validly associated with neurons.

The **(i) button** to the left of **Show All** displays this introduction at any time. **Description…** and **Test Results…** open the same project information and evaluation as in the normal Explore window.

### Editing and exploring

- In **Edit** mode, cards, graphics, comments, shapes, and the binary input array can be selected, moved, resized, colored, aligned, copied, and removed.
- In **Explore** mode, input controls and binary array cells can be operated. Layout objects are protected from accidental movement.
- The window opens in Explore mode. Switch to Edit mode only when the presentation is to be changed.

In the **Design** menu, **Show Grid** displays a layout grid. **Grid Spacing…** sets its spacing between 5 and 200 pixels. The setting is stored with the project, but the grid is visible only in Edit mode and is automatically hidden while exploring.

Right-click an empty area and use **Add Element** to add individual inputs, outputs, a binary input array, a background graphic, a comment, or a graphical shape. **Add all inputs and outputs** adds every neuron card that is not yet visible in one step without creating duplicates. Elements can later be removed from the layout without deleting their neurons from the project. Removal requires confirmation.

### Input and output cards

Analog input cards contain the value in its original unit and a slider. Binary inputs contain an On/Off switch. Output cards can display an analog bar, a semicircular gauge, or a binary decision. For analog outputs, the scale limits come from the assigned calibration. For binary outputs, **Show Intermediate Values** replaces the compact decision display with the numerical network value and its interpreted 0/1 state.

Cards can be resized. Their background color can be set individually or transferred to a selected group. Several selected input cards or output cards can also receive a common size and alignment.

### Binary input array

If the training data define a two-dimensional binary input array, it can be inserted as one independent layout element. Its cells remain linked to their input neurons. In Explore mode the cells switch the corresponding binary inputs; tooltips identify the associated neurons. Colors for the On and Off states can be chosen separately.

### Graphics, comments, and shapes

A picture can be loaded from a file, dragged into the window, or pasted from the clipboard. When the layout is saved, NeuronNetz copies it into the project area and stores its position and size. Selecting the picture and pressing **Delete** performs the same confirmed removal as the menu command.

Comments provide freely placeable explanatory text with configurable font, alignment, text color, background, and frame. Lines, rectangles, and ellipses can be used to group or connect parts of the presentation. Their line color, width, and optional transparent or colored fill are stored in the layout. A line can show an arrowhead at its end; **Reverse arrow direction** moves it to the opposite endpoint. These graphical elements remain behind the interactive input and output cards.

### Selecting, arranging, and navigating

Drag a selection rectangle around elements in Edit mode. Only elements completely enclosed by the rectangle are selected. Selected elements have a red outline. They can be moved together, nudged pixel by pixel with the arrow keys, aligned, distributed, copied with **Ctrl+C**, and pasted with **Ctrl+V**. Copy and paste apply only to graphical layout elements, not to neuron input and output cards.

Use the mouse wheel to zoom around the pointer. Pan with **Alt+Drag** or the closed hand after zooming. **Show All** fits the current layout into the available area. The status line reports the zoom level. Window size, zoom, element positions, sizes, colors, and visibility are saved with the project.

**Ctrl+S** saves the graphical layout. The Save button is disabled while no layout change is pending. Closing the window or pressing **Esc** asks whether unsaved changes should be saved. **Default Layout** resets card positions and sizes after confirmation but keeps the background graphic.

The layout is stored in the project under `grafisches_experiment/layout.json`. It remains readable JSON and contains presentation settings only; the neural network itself remains in the `.nnproj` project file.

# 24. Debugging Training

The training debugger examines one learning step with forward and backward calculation. It shows inputs, sums, activations, errors, deltas, and changes to weights and biases. With momentum enabled, the preceding velocity, momentum contribution, and new velocity are part of the calculation.

Use it when a network does not learn or when a result needs mathematical explanation. The state from opening the debugger can be restored.

# 25. Mathematics Mode

Mathematics Mode deliberately processes training records one by one and works on an experimental copy of the network.

1. Select a neuron.
2. Set learning rate, momentum, display precision, and starting method.
3. Click **Start Experiment**.
4. Follow Starting Values, Inputs, Weighted Sum, Activation, Error/Delta, New Parameters, and Result.
5. Continue with the next record or epoch.

Hidden neurons show backward sum, derivative, and hidden delta; output neurons show target, error, and output delta. Parameter updates list the gradient, preceding velocity, momentum contribution, and new velocity separately. **Full Report** contains the complete calculation. Undo operations also restore momentum states. Closing Mathematics Mode restores the original project state.

# 26. Saving and Opening Projects

**Save** writes the project to its existing path. **Save As** can create a dedicated project folder:

```text
ProjectName/
├── ProjectName.nnproj
├── trainingsdaten/
├── testdaten/
└── exporte/
```

Choose the preferred project folder under **Program Settings → Editor → Project Folder**. Without a custom choice, the German interface uses `Projects_de` and the English interface uses `Projects_en`. A selected folder can be used independently of the interface language.

# 27. Training and Test Data Files

Training and test data are stored as `.nndata` files. Assigned files can be saved with the project or copied into a new project folder during **Save As**.

Relative references inside a structured project folder make the complete project easier to move. Missing data files are reported when opening and can be selected again.

# 28. Project Information and Report

**Project Description** stores formatted text directly in the project. **Project Overview** summarizes structure, data, and training state. **Project Workflow** guides the user through important steps.

The project report can be exported as a Word or PDF document. Language and file format follow the selected settings or save dialog.

# 29. Example Projects and Project Assistant

**File → Example Projects** searches the currently selected project folder for marked examples. German and English project collections can be selected independently of the interface language.

The project assistant helps develop original ideas. It creates an editable prompt for an external AI containing project description, inputs, outputs, ranges, foundations, network proposal, and tab-separated training data. NeuronNetz does not send data to an external service.

# 30. Typical Problems

**Training does not start:** validate the network, check assignments, and ensure complete numeric records.

**Network does not learn:** check scaling, activation functions, learning rate, targets, and initialization.

**Error fluctuates strongly:** reduce the learning rate and inspect data for outliers.

**Targets cannot be reached:** check the output activation function's range.

**Project or data file is missing:** move the complete project folder and reassign the missing file.

**Display is cluttered:** arrange the network, hide weight values, or use zoom and Show All.

# 31. Keyboard Shortcuts

- **Ctrl+N:** New Project
- **Ctrl+O:** Open Project
- **Ctrl+S:** Save
- **Ctrl+Shift+S:** Save As
- **Ctrl+Z:** Undo
- **Ctrl+Y:** Redo
- **Ctrl+X / Ctrl+C / Ctrl+V:** Cut, copy, paste
- **Delete:** Delete selection
- **Alt+F4:** Exit program

# 32. Mathematical Foundations

For a neuron, in simplified form:

```text
Σ = Sum(Input × Weight) + Bias
Y = ActivationFunction(Σ)
```

Training derives an error from target and output. Backpropagation calculates deltas and corrects weights and biases against the error gradient. The learning rate controls the size of this correction.

Sigmoid returns values from 0 to 1, Tanh from −1 to 1, ReLU maps negative sums to 0, and Linear passes the sum through unchanged.

# 33. Training History

Training history is saved per project with initialization, mode, learning rate, momentum, epoch count, error after the first epoch, final error, maximum individual error, duration, and a compact error curve. Several runs can be selected and compared with a linear or logarithmic Y axis.

The **Initialization** column distinguishes a new Xavier/Glorot start, a continued run, and a run repeated with stored starting conditions. Repeating with the same starting conditions restores weights, biases, and training-record order. If learning rate and momentum also remain unchanged, the curves should lie exactly on top of each other. Changing either parameter deliberately produces a comparable run from the same starting point.

Runs can be exported to CSV, deleted, or restored when compatible with the current network structure.

If all runs are deleted, result values and curve disappear from the open training window. Current network weights and biases remain unchanged.

# 34. Illustrated Manual

This Markdown file is the integrated operational reference. The illustrated manual supplements it with screenshots, marked controls, and complete examples.

Use **Help → Tutorials** to select and open the German or English manual as a Word or PDF file with the associated Windows application. NeuronNetz remembers the most recently selected tutorial folder.
