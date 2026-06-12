"""MDIAreaQtFigure: A pyqtgraph-based figure widget for HDF5 data visualization."""

from __future__ import annotations

from typing import Generator
import numpy as np
from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtGui import QAction
import pyqtgraph as pg

# Local modules
from src.utils.bus_event import bus
from src.domain.models import FileNode
from src.utils.ressource_path import resource_path

from pyqt_widget_kit import IconButton, StringFilterLineEdit
from .settings import SettingsWindow
from .pyqt_graph import BaseFigureWidget


class ScatterFigureWidget(BaseFigureWidget):
    """
    A custom widget providing an interactive scatter plot with clickable points.
    Emits signals when points are clicked and provides methods to manage the plot.
    Also supports rectangular selection of multiple points.
    """
    # Signal emitted when a data point is clicked
    pointClicked = QtCore.pyqtSignal(float, float, str, int, str, str)  # x, y, series_name, index, filename, file_path
    
    # Signal emitted when multiple points are selected via rectangle
    pointsSelected = QtCore.pyqtSignal(list)  # list of dicts with point data
    
    def __init__(self, parent=None) -> None:
        super().__init__(parent, with_legend=True)
        
        # Set default parameters
        self.files = []  # List of HDF5 files to process
        self.regex_y = ""  # Regex to match Y values
        self.regex_x = ""  # Regex to match X values, if empty use indices
        self.group_by = ""  # Regex to group datasets
        self.filter = ""  # Filter by attribute value
        self.progress_callback = None  # Callback for progress reporting
        self.settings = {
            'mode': 'markers',
            'line_width': 1,
            'marker_size': 6,
            'show_grid_x': True,
            'show_grid_y': True,
        }
        self.scatter_items = []
        self.datasets = []
        
        self._init_ui()
        
    def _init_ui(self) -> None:
        
        # Create a highlight point (initially invisible)
        self.highlight = pg.ScatterPlotItem(
            size=15,
            pen=pg.mkPen('k', width=2),
            brush=pg.mkBrush(255, 255, 0, 200),
            symbol='o',
            visible=False
        )
        self.plot.addItem(self.highlight)
        
        # Create a highlight for multiple selected points (initially invisible)
        self.multi_highlight = pg.ScatterPlotItem(
            size=15,
            pen=pg.mkPen('r', width=2),
            brush=pg.mkBrush(255, 100, 100, 200),
            symbol='o',
            visible=False
        )
        self.plot.addItem(self.multi_highlight)
        
        # Add rectangle selection tool
        self.selection_roi = pg.RectROI([0, 0], [1, 1], pen=pg.mkPen('g', width=2))
        self.selection_roi.setZValue(10)  # Ensure it's on top of other items
        self.selection_roi.addScaleHandle([0, 0], [1, 1])
        self.selection_roi.addScaleHandle([1, 1], [0, 0])
        self.selection_active = False  # Flag to track if selection mode is active
    
    def clear(self) -> None:
        """Clear all plots and data"""
        # Disable rectangle selection if active
        if self.selection_active:
            self.enable_rectangle_selection(False)
            
        # Remove existing line curves and scatter items
        self.clear_trace()
        for scatter in self.scatter_items:
            try:
                self.plot.removeItem(scatter)
            except Exception:
                pass

        if self.legend:
            self.legend.clear()
        self.scatter_items = []
        self.datasets = []
        
        # Re-add the highlight points after clearing
        if self.highlight not in self.plot.items():
            self.plot.addItem(self.highlight)
        self.highlight.setData(visible=False)
        if self.multi_highlight not in self.plot.items():
            self.plot.addItem(self.multi_highlight)
        self.multi_highlight.setData(visible=False)
        
    def set_filter(self, filter_str: str) -> None:
        """
        Set a filter string to filter datasets on attributes values. The filter string is composed of
        conditions separated by ';'. Each condition is of the form 'attribute_regex operator value', where 
        operator is one of ==, !=, <, <=, >, >=.
        Example: settings/ap*==3;settings/ae/unit='mm'
        """
        
        if not isinstance(filter_str, str):
            filter_str = ''
            
        filter_str = filter_str.strip()
        
        # Check if filter changed
        if filter_str == self.filter:
            return
        
        # Check filter syntax
        for cond in self._split_filter(filter_str):
            if 'attr_regex' not in cond or 'operator' not in cond or 'value' not in cond:
                bus.log_info(f"Warning: Invalid filter condition '{cond}'. Ignoring filter.")
                return
            # Check if attr_regex is a valid regex
            import re
            try:
                re.compile(cond['attr_regex'])
            except re.error as ex:
                bus.log_info(f"Warning: Invalid regex in filter condition '{cond['attr_regex']}': {ex}. Ignoring filter.")
                return

        # Commit filter
        self.filter = filter_str
        
    def _split_filter(self, filter_string) -> Generator[dict, None, None]:
        import re
        
        pat = r'(.*?)(==|!=|>=|<=|<|>)(.*)'
        reg = re.compile(pat)
        
        for f in filter_string.split(';'):
            f = f.strip()
            if not f:
                continue
            m = reg.match(f)
            if not m:
                continue
            attr_regex, operator, value = m.groups()
            attr_regex = attr_regex.strip()
            value = value.strip().strip("'\"")  # remove quotes if any
            if not attr_regex or not operator or not value:
                continue
            yield {'attr_regex': attr_regex, 'operator': operator, 'value': value}
        
    def set_group_by(self, group_by: str) -> None:
        """
        Set the attribute name to group datasets by. Datasets with the same value for this attribute
        will be plotted in the same series.
        """
        
        if not isinstance(group_by, str):
            group_by = ''
            
        group_by = group_by.strip()
        
        # Check if group_by changed
        if group_by == self.group_by:
            return
        
        if '\\' in group_by:
            group_by = group_by.replace('\\', '/')
            
        if group_by.startswith('/'):
            group_by = group_by[1:]
            
        if group_by.endswith('/'):
            group_by = group_by[:-1]
            
        # Check if group_by is a valid regular expression
        import re
        if group_by:
            try:
                re.compile(group_by)
            except re.error as ex:
                bus.log_info(f"Warning: Invalid group_by regex '{group_by}': {ex}. Ignoring group_by.")
                return  
            
        # Commit group_by
        self.group_by = group_by
    
    def add_points(self, x_values, y_values, series_name="Series", color=(0, 0, 0), **kwargs) -> list:
        """
        Add multiple points to the plot at once.
        
        Parameters:
        -----------
        x_values : array-like
            X values for the points
        y_values : array-like
            Y values for the points
        series_name : str
            Name of the series these points belong to
        color : tuple
            RGB color tuple (r, g, b) with values 0-255
        
        Returns:
        --------
        indices : list
            The indices of the added points in their series
        """
        # Convert to numpy arrays
        x_values = np.asarray(x_values, dtype=float)
        y_values = np.asarray(y_values, dtype=float)
        
        if len(x_values) != len(y_values):
            raise ValueError("x_values and y_values must have the same length")
        
        if len(x_values) == 0:
            return []
        
        # Check if this series already exists
        series_found = False
        series_idx = -1
        
        for i, dataset in enumerate(self.datasets):
            if dataset['name'] == series_name:
                series_found = True
                series_idx = i
                break
        
        # If series doesn't exist, create it
        if not series_found:
            self.datasets.append({
                'name': series_name,
                'x': x_values,
                'y': y_values,
                'color': color
            })
            
            # Create new curve for this series
            linewidth = int(self.settings.get('line_width', 1))
            mode = self.settings.get('mode', 'markers')
            marker_size = int(self.settings.get('marker_size', 6))
            if mode not in ('lines', 'markers', 'lines+markers'):
                mode = 'markers'
            pen = pg.mkPen(color[0], color[1], color[2], width=linewidth) if ('lines' in mode) else None
            curve = self.plot.plot(
                x_values, 
                y_values, 
                pen=pen, 
                name=series_name,
                symbol='o' if 'markers' in mode else None,
                symbolSize=marker_size
            )
            self._curves.append(curve)
            
            # Create scatter for this series
            scatter = pg.ScatterPlotItem(
                size=marker_size,
                pen=pg.mkPen(None),
                brush=pg.mkBrush(color[0], color[1], color[2], 200),
                symbol='o',
            )
            
            # Connect the scatter's click signal
            scatter.sigClicked.connect(self.on_point_clicked)
            
            # Add scatter to the plot
            self.plot.addItem(scatter)
            self.scatter_items.append(scatter)
            
            # Add points
            points = []
            
            # Check if we have file information passed in
            files = kwargs.get('files', [None] * len(x_values))
            file_paths = kwargs.get('file_paths', [None] * len(x_values))
            
            for i, (x, y) in enumerate(zip(x_values, y_values)):
                file_info = files[i] if i < len(files) else None
                file_path_info = file_paths[i] if i < len(file_paths) else None
                
                points.append({
                    'pos': (x, y),
                    'data': {
                        'series': series_name, 
                        'index': i, 
                        'x': x, 
                        'y': y,
                        'file': file_info,
                        'filepath': file_path_info
                    }
                })
            scatter.addPoints(points)
            
            # Return indices
            indices = list(range(len(x_values)))
            
        else:
            # Series exists, append to it
            dataset = self.datasets[series_idx]
            curve = self._curves[series_idx]
            scatter = self.scatter_items[series_idx]
            
            # Get starting index for new points
            start_idx = len(dataset['x'])
            
            # Append to data arrays
            dataset['x'] = np.append(dataset['x'], x_values)
            dataset['y'] = np.append(dataset['y'], y_values)
            
            # Update the curve
            curve.setData(dataset['x'], dataset['y'])
            
            # Add points to scatter
            points = []
            for i, (x, y) in enumerate(zip(x_values, y_values)):
                idx = start_idx + i
                points.append({
                    'pos': (x, y),
                    'data': {'series': series_name, 'index': idx, 'x': x, 'y': y}
                })
            scatter.addPoints(points)
            
            # Return indices
            indices = list(range(start_idx, start_idx + len(x_values)))
        
        # Update view
        self.plot.autoRange()
        
        return indices    

    def read_files(self) -> None:
        """Read datasets from an HDF5 file and plot them"""
        import h5kit as h5
        import os
        
        # Open all files, filter based on hdf5 attributes and group by attribute if specified
        all_datasets = []
        
        # Process all files in the list
        total_files = len(self.files)
        
        for file_idx, file in enumerate(self.files):
            
            # Report progress if callback is set
            if self.progress_callback is not None:
                if not self.progress_callback(file_idx, total_files, file):
                    print("File processing canceled by user")
                    return
            
            if not h5.is_hdf5_file(file):
                print(f"Error: File {file} is not a valid HDF5 file. Skipping.")
                continue
            
            with h5.File(file, 'r') as f:
                
                # Filter out file if does not match filter
                if self.filter:
                    
                    attr_match_found = False
                    for cond in self._split_filter(self.filter):
                        attr_regex = cond['attr_regex']
                        operator = cond['operator']
                        value = cond['value']
                        attrs = f.find_attr_by_regex(attr_regex)
                        if not attrs or len(attrs) == 0:
                            break
                        # If multiple attributes match, we consider it a match if any one matches the condition
                        for attr in attrs:
                            # Try numeric conversion first, then string comparison
                            attr_value = attr
                            try:
                                # Try numeric comparison if possible
                                attr_value_num = float(attr_value)
                                value_num = float(value)
                                if operator == '==':
                                    if attr_value_num == value_num:
                                        attr_match_found = True
                                        break
                                elif operator == '!=':
                                    if attr_value_num != value_num:
                                        attr_match_found = True
                                        break
                                elif operator == '<':
                                    if attr_value_num < value_num:
                                        attr_match_found = True
                                        break
                                elif operator == '<=':
                                    if attr_value_num <= value_num:
                                        attr_match_found = True
                                        break
                                elif operator == '>':
                                    if attr_value_num > value_num:
                                        attr_match_found = True
                                        break
                                elif operator == '>=':
                                    if attr_value_num >= value_num:
                                        attr_match_found = True
                                        break
                            except Exception:
                                # Fallback to string comparison
                                attr_value_str = str(attr_value)
                                if operator == '==':
                                    if attr_value_str == value:
                                        attr_match_found = True
                                        break
                                elif operator == '!=':
                                    if attr_value_str != value:
                                        attr_match_found = True
                                        break
                                else:
                                    # Skip this attribute for non-numeric operators
                                    continue
                            
                    # If no attribute matched this condition, file doesn't match filter
                    if not attr_match_found:
                        continue
            
                value = f.find_attr_by_regex(self.regex_y)
                if value is None or len(value) == 0:
                    print(f"Warning: No attribute matching regex '{self.regex_y}' found in file {file}. Skipping.")
                    continue
                
                if len(value) > 1:
                    print(f"Warning: Multiple attributes matching regex '{self.regex_y}' found in file {file}. Using the first one.")
                
                value = value[0]
                try:
                    y = float(value)
                except ValueError:
                    print(f"Warning: Attribute '{self.regex_y}' in file {file} is not numeric. Skipping.")
                    continue
                
                x = None
                
                if self.regex_x:
                    value = f.find_attr_by_regex(self.regex_x)
                    
                    if value is None:
                        print(f"Warning: No attribute matching regex '{self.regex_x}' found in file {file}. Using index as x.")
                    
                    if len(value) > 1:
                        print(f"Warning: Multiple attributes matching regex '{self.regex_x}' found in file {file}. Using the first one.")
                        
                    value = value[0]
                    try:
                        x = float(value)
                    except ValueError:
                        print(f"Warning: Attribute '{self.regex_x}' in file {file} is not numeric. Using index as x.")
                        x = None
                        
                if x is None:
                    x = len(all_datasets)
                    
                # Determine series name based on grouping attribute if specified
                series_name = "Series 1"
                if self.group_by:
                    group_value = f.find_attr_by_regex(self.group_by)
                    if group_value and len(group_value) > 0:
                        series_name = str(group_value[0])
                        
                # Get filename without full path for display
                display_filename = os.path.basename(file)
                all_datasets.append({
                    'x': x, 
                    'y': y, 
                    'series': series_name,
                    'file': display_filename,  # Add filename to dataset
                    'filepath': file  # Also store full path
                })
                
        # Return empty list if no datasets found
        if not all_datasets or len(all_datasets) == 0:
            bus.log_info("No datasets found to plot, check filter string.")
            return
            
        # Complete progress if callback is set
        if self.progress_callback is not None:
            self.progress_callback(total_files, total_files, "Processing complete")
            self.progress_callback = None  # Reset callback after completion
        
        # Group datasets by series
        series_dict = {}
        for data in all_datasets:
            series = data['series']
            if series not in series_dict:
                series_dict[series] = {'x': [], 'y': [], 'files': [], 'filepaths': []}
            series_dict[series]['x'].append(data['x'])
            series_dict[series]['y'].append(data['y'])
            series_dict[series]['files'].append(data['file'])  # Add filename 
            series_dict[series]['filepaths'].append(data['filepath'])  # Add full path
        
        # Add each series to the plot if requested
        for i, (series, data) in enumerate(series_dict.items()):
            color = pg.intColor(i, hues=len(series_dict))
            rgb = (color.red(), color.green(), color.blue())
            self.add_points(
                data['x'], 
                data['y'], 
                series_name=series, 
                color=rgb,
                files=data.get('files', []),
                file_paths=data.get('filepaths', [])
            )

    def on_point_clicked(self, scatter, points) -> None: 
        """Handle scatter point clicks"""
        
        # Handle empty points array (works with both list and numpy.ndarray)
        if points is None or len(points) == 0:
            return
            
        # Get the first clicked point
        point = points[0] 
        
        # Extract point information
        point_data = point.data()
        x, y = point.pos()
        series_name = point_data.get('series', '')
        point_index = point_data.get('index', -1)
        filename = point_data.get('file', '')
        filepath = point_data.get('filepath', '')
        
        # Show information in the info label
        info_text = f"Series: {series_name}, Point #{point_index}, X: {x:.2f}, Y: {y:.2f}, File: {filename}"
        bus.log_info(info_text)
        
        # Highlight the clicked point
        self.highlight.setData(x=[x], y=[y], visible=True)
        
        # Emit the signal with filename
        self.pointClicked.emit(x, y, series_name, point_index, filename, filepath)
    
    def clear_highlight(self) -> None:
        """Clear all highlighted points"""
        self.highlight.setData(visible=False)
        self.multi_highlight.setData(visible=False)
        
        if hasattr(self, 'selection_active') and self.selection_active:
            bus.log_info("Drag the green rectangle to select points")
        else:
            bus.log_info("Click on points to see their data")
    
    def highlight_point(self, x, y) -> None:
        """Highlight a specific point"""
        self.highlight.setData(x=[x], y=[y], visible=True)
    
    def enable_rectangle_selection(self, enable=True) -> None:
        """Enable or disable rectangle selection mode"""
        if enable and not self.selection_active:
            # Clear any currently highlighted points
            self.highlight.setData(visible=False)
            self.multi_highlight.setData(visible=False)
            
            # Add the ROI to the plot and connect its signals
            self.plot.addItem(self.selection_roi)
            self.selection_roi.sigRegionChangeFinished.connect(self.on_selection_changed)
            self.selection_active = True
            
            # Position the ROI in the center of the view
            view_range = self.plot.viewRange()
            x_center = (view_range[0][0] + view_range[0][1]) / 2
            y_center = (view_range[1][0] + view_range[1][1]) / 2
            x_width = (view_range[0][1] - view_range[0][0]) / 4
            y_height = (view_range[1][1] - view_range[1][0]) / 4
            
            self.selection_roi.setPos([x_center - x_width/2, y_center - y_height/2])
            self.selection_roi.setSize([x_width, y_height])
            
            # Set info text
            bus.log_info("Drag the green rectangle to select points")
            
        elif not enable and self.selection_active:
            # Remove the ROI from the plot and disconnect signals
            self.plot.removeItem(self.selection_roi)
            try:
                self.selection_roi.sigRegionChangeFinished.disconnect(self.on_selection_changed)
            except TypeError:
                # Ignore if not connected
                pass
            self.selection_active = False
            
            # Clear any multi-selection highlights
            self.clear_multi_selection()
            bus.log_info("Click on points to see their data")
    
    def clear_multi_selection(self) -> None:
        """Clear multi-selection highlights"""
        self.multi_highlight.setData(visible=False)
    
    def on_selection_changed(self) -> None:
        """Handle when the selection rectangle is changed"""
        if not self.selection_active:
            return
            
        # Get the ROI region in plot coordinates
        rect = self.selection_roi.boundingRect()
        roi_pos = self.selection_roi.pos()
        
        x_min = roi_pos[0]
        x_max = roi_pos[0] + rect.width()
        y_min = roi_pos[1]
        y_max = roi_pos[1] + rect.height()
        
        # Find all points that fall within the rectangle
        selected_points = []
        x_coords = []
        y_coords = []
        
        for series_idx, scatter in enumerate(self.scatter_items):
            points = scatter.points()
            
            for point in points:
                x, y = point.pos()
                
                if x_min <= x <= x_max and y_min <= y <= y_max:
                    # Point is within rectangle selection
                    point_data = point.data()
                    selected_points.append(point_data)
                    x_coords.append(x)
                    y_coords.append(y)
        
        # Highlight all selected points
        if selected_points:
            self.multi_highlight.setData(x=x_coords, y=y_coords, visible=True)
            
            # Emit signal with selected points
            self.pointsSelected.emit(selected_points)
        else:
            # No points selected
            self.multi_highlight.setData(visible=False)
    
    def toggle_rectangle_selection(self) -> None:
        """Toggle rectangle selection mode on/off"""
        self.enable_rectangle_selection(not self.selection_active)


class MDIScatter(QtWidgets.QMdiSubWindow):
    explorerSelectionRequested = QtCore.pyqtSignal(list)
    
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.setWindowTitle("Plot (pyqtgraph)")
        windowFlags = QtCore.Qt.WindowType.Window
        windowFlags &= ~QtCore.Qt.WindowType.WindowMinMaxButtonsHint
        windowFlags |= QtCore.Qt.WindowType.WindowCloseButtonHint
        self.setWindowFlags(windowFlags)

        self.fig = ScatterFigureWidget()
        
        # Connect the pointsSelected signal
        self.fig.pointsSelected.connect(self.on_points_selected)
        self.fig.pointClicked.connect(self.on_point_clicked)

        container = QtWidgets.QWidget()
        self.main_layout = QtWidgets.QVBoxLayout(container)
        self.main_layout.setSpacing(0)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.addWidget(self.fig)

        # top bar (reuse your custom widgets)
        self.button_menu = IconButton(icon=resource_path('./src/ico/burger.png'))
        self.button_menu.setToolTip("Menu")
        self.button_menu.setMenu(self.init_menu())
        
        self.button_settings = IconButton(icon=resource_path('./src/ico/settings.png'))
        self.button_settings.setToolTip("Plot Settings")
        self.button_settings.clicked.connect(self.show_settings)

        self.button_tree = IconButton(icon=resource_path('./src/ico/tree.png'))
        self.button_tree.setCheckable(True)
        self.button_tree.setToolTip("Plot Tree Selection")
        
        self.button_clear = IconButton(icon=resource_path('./src/ico/eraser.png'))
        self.button_clear.setToolTip("Clear Plot")
        self.button_clear.clicked.connect(self.fig.clear)

        self.menu_layout = QtWidgets.QHBoxLayout()
        self.menu_layout.setContentsMargins(1, 1, 1, 1)
        self.menu_layout.setSpacing(1)
        self.menu_layout.addWidget(self.button_tree)
        self.menu_layout.addWidget(self.button_clear)
        self.menu_layout.addWidget(self.button_menu)
        self.menu_layout.addWidget(self.button_settings)
        self.menu_layout.addStretch(1)

        self.menu = QtWidgets.QWidget(container)
        self.menu.setLayout(self.menu_layout)

        # Float the menu on top of the graph without consuming layout space
        self.menu_container = QtWidgets.QFrame(container)
        self.menu_container.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        overlay_layout = QtWidgets.QVBoxLayout(self.menu_container)
        overlay_layout.setContentsMargins(4, 4, 4, 4)
        overlay_layout.setSpacing(0)
        overlay_layout.addWidget(self.menu)
        self.menu_container.adjustSize()
        self.menu_container.raise_()
        self._position_menu()
        self.menu_container.hide()

        self.setWidget(container)

    def enterEvent(self, event: QtCore.QEvent) -> None:
        """Show the floating menu when the cursor enters the window."""
        self.menu_container.show()
        super().enterEvent(event)

    def leaveEvent(self, event: QtCore.QEvent) -> None:
        """Hide the floating menu when the cursor leaves the window."""
        self.menu_container.hide()
        super().leaveEvent(event)

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        """Keep the floating menu anchored during resizes."""
        self._position_menu()
        super().resizeEvent(event)

    def _position_menu(self) -> None:
        """Position the floating menu in the top-right corner."""
        margin = 4
        parent = self.widget() or self
        if not parent:
            return
        self.menu_container.adjustSize()
        menu_size = self.menu_container.size()
        x = max(margin, parent.width() - menu_size.width() - margin)
        y = margin
        self.menu_container.move(x, y)
        
    def closeEvent(self, event: QtGui.QCloseEvent | None) -> None:
        """Handle window close event and clean up resources."""
        if event is None:
            return
        
        # Disconnect signals from the scatter widget
        try:
            self.fig.pointsSelected.disconnect(self.on_points_selected)
            self.fig.pointClicked.disconnect(self.on_point_clicked)
        except TypeError:
            # Signals might already be disconnected
            pass
        
        # Clear plot data
        self.fig.clear()
        
        # Accept the close event
        event.accept()
        super().closeEvent(event)
        
    def init_menu(self) -> QtWidgets.QMenu:
        """Display our custom menu at the specified position"""
        
        menu = QtWidgets.QMenu(self)

        # Create and add standard actions
        clear_action = QAction("Clear", self)
        clear_action.triggered.connect(self.fig.clear)
        menu.addAction(clear_action)
        
        save_action = QAction("Save (PNG)", self)
        save_action.triggered.connect(self.save_plot_png)
        menu.addAction(save_action)
        
        close_action = QAction("Close Window", self)
        close_action.triggered.connect(self.close)
        menu.addAction(close_action)
        
        menu.addSeparator()
        
        # Create rectangle selection action
        self.rect_select_action = QAction("Enable Rectangle Selection", self)
        self.rect_select_action.setCheckable(True)
        self.rect_select_action.toggled.connect(self.toggle_rectangle_selection)
        menu.addAction(self.rect_select_action)

        return menu
        
    def toggle_rectangle_selection(self, checked) -> None:
        """Toggle rectangle selection mode on/off"""
        self.fig.enable_rectangle_selection(checked)
        if checked:
            self.rect_select_action.setText("Disable Rectangle Selection")
        else:
            self.rect_select_action.setText("Enable Rectangle Selection")
    
    def on_point_clicked(self, x, y, series_name, point_index, filename, filepath) -> None:
        """Handle when a single point is clicked"""
        if filepath and not self.button_tree.isChecked():
            self.explorerSelectionRequested.emit([filepath])
        
    def on_points_selected(self, points) -> None:
        """Handle when multiple points are selected via rectangle"""
        if not points:
            return
        
        # Get file paths from selected points
        file_paths = []
        for point_data in points:
            if 'filepath' in point_data:
                file_path = point_data.get('filepath')
                if file_path:
                    file_paths.append(file_path)
        
        # Select corresponding nodes in the tree view if tree button is checked
        if file_paths and not self.button_tree.isChecked():
            self.explorerSelectionRequested.emit(file_paths)
        
    def save_plot_png(self) -> None:
        # Export a PNG using pyqtgraph exporter
        fname, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save Plot", "", "PNG Files (*.png);;All Files (*)")
        if not fname:
            return
        try:
            from pyqtgraph.exporters import ImageExporter
            exp = ImageExporter(self.fig.plot.plotItem)
            exp.parameters()['width'] = 1920  # upscale for retina
            exp.export(fname)
        except Exception as ex:
            bus.log_info(f"Error saving PNG: {ex}")
            
    def show_settings(self) -> None:
        """Show the plot settings dialog."""
        self.settings_window = ScatterPlotSettingsWindow(self.fig)
        self.settings_window.show()
        
    def tree_selection_changed(self, nodes: FileNode | list[FileNode] | tuple[FileNode, ...] | None) -> None:
        """
        Handle the event when an item is selected in the explorer tree.
        This method reads the selected HDF5 file and plots the datasets based on the current regex settings.
        Parameters:
            path (str): The path of the selected item in the explorer tree.
        """
        
        if self.button_tree.isChecked() is False:
            return
        
        if nodes is None:
            return
        
        paths = []
        if isinstance(nodes, (list, tuple)):
            for node in nodes:
                if isinstance(node, FileNode) and (not node.disable) and (node.path not in paths):
                    paths.append(node.path)
        elif isinstance(nodes, FileNode):
            if nodes.disable:
                return
            paths.append(nodes.path)
        else:
            return
        
        # Clear existing plot
        self.fig.clear()
        self.fig.files = paths
        self.fig.read_files()


class ScatterPlotSettingsWindow(SettingsWindow):
    """
    Settings window for configuring plot appearance and data selection.
    Provides controls for data filtering, axis formatting, and plot style.
    """
    title = "Scatter Plot Settings"
    
    def __init__(self, graph_view: ScatterFigureWidget) -> None:
        """
        Initialize the settings window with a reference to the graph view.
        
        Parameters:
        -----------
        graph_view : The graph view widget containing plot configuration and data
        """
        super().__init__()
        
        # Inner variables
        self.fig = graph_view
        
        # Buttons
        self.okButton = self.add_button("Done", self.close, validate=True)
        self.applyButton = self.add_button("Apply", self.apply, validate=True)
        
        self._init_settings()
        
    def _init_settings(self) -> None:
        """Set up all UI controls for the plot settings window."""
        data = self.add_section("Data")
        formatting = self.add_section("Formatting")
        formatting_title = formatting.add_section("Title")
        formatting_axis = formatting.add_section("Axis")
        formatting_plot_type = formatting.add_section("Plot Type")

        self._regex_x = data.add_regex(
            key='scatter.regex_x',
            title='X Data',
            value=self.fig.regex_x,
            subtitle='Enter python regular expression',
            description='Use a python regular expression to capture data that will be used as X values.',
        ).widget

        self._regex_y = data.add_regex(
            key='scatter.regex_y',
            title='Y Data',
            value=self.fig.regex_y,
            subtitle='Enter Python regular expression',
            description='Use a python regular expression to capture data that will be used as Y values.',
        ).widget

        self._filter = StringFilterLineEdit()
        self._filter.setText(self.fig.filter)
        data.add_widget(
            key='scatter.dataset_filter',
            title='Dataset Filter',
            subtitle='String that filters datasets based on attribute values.',
            description=(
                "Use the following notation to filter out data from selection.\n"
                "Allowed operators are '==' '!=' '<' '<=' '>' '>='. ';' can be used to separate filters.\n"
                "Example of use: settings/ap*==3;settings/ae/unit='mm'"
            ),
            widget=self._filter,
            validator=lambda _value: None if self._filter.isValid() else "Enter a valid dataset filter.",
        )

        self._group_by = data.add_regex(
            key='scatter.group_by',
            title='Group By Attribute',
            value=self.fig.group_by,
            subtitle='String that allows to group-by data series based on attribute values.',
            description=(
                "Provide a python regular expression to group data series based on attribute values. "
                "Datasets with the same attribute value will be grouped together in the same series."
            ),
        ).widget

        self._show_legend = formatting.add_bool(
            key='scatter.show_legend',
            title='Show Legend',
            value=self.fig.legend.isVisible(),
            subtitle='Toggle the visibility of the legend on the plot.',
            description="Check to display the legend that identifies different data series on the plot.",
        ).widget
        self._show_legend.setText("Show legend")

        self._show_grid_x = formatting.add_bool(
            key='scatter.show_grid_x',
            title='Show Grid X',
            value=bool(self.fig.settings.get('show_grid_x', True)),
            subtitle='Toggle X-axis grid lines.',
            description='Check to display vertical grid lines on the plot for better readability.',
        ).widget
        self._show_grid_x.setText("Show grid X")

        self._show_grid_y = formatting.add_bool(
            key='scatter.show_grid_y',
            title='Show Grid Y',
            value=bool(self.fig.settings.get('show_grid_y', True)),
            subtitle='Toggle Y-axis grid lines.',
            description='Check to display horizontal grid lines on the plot for better readability.',
        ).widget
        self._show_grid_y.setText("Show grid Y")

        title_text = self.fig.plot.windowTitle()
        self._title = formatting_title.add_text(
            key='scatter.plot_title',
            title='Plot Title',
            value=title_text,
            subtitle='Set the plot title.',
            description='Enter a custom title for your plot. This will appear at the top of the plot area.',
        ).widget

        x_text = self.fig.plot.getAxis('bottom').labelText
        self._x_title = formatting_axis.add_text(
            key='scatter.x_axis_title',
            title='X Axis Title',
            value=x_text,
            subtitle='Set the X-axis label.',
            description='Enter a label for the X-axis to describe the data shown horizontally.',
        ).widget

        y_text = self.fig.plot.getAxis('left').labelText
        self._y_title = formatting_axis.add_text(
            key='scatter.y_axis_title',
            title='Y Axis Title',
            value=y_text,
            subtitle='Set the Y-axis label.',
            description='Enter a label for the Y-axis to describe the data shown vertically.',
        ).widget

        mode = self.fig.settings.get('mode', 'markers')
        if mode not in ('markers', 'lines', 'lines+markers'):
            mode = 'markers'
        self.mode = formatting_plot_type.add_choice(
            key='scatter.mode',
            title='Plot Type',
            options=['markers', 'lines', 'lines+markers'],
            value=mode,
            subtitle='Choose the plot style.',
            description='Select whether to display data as lines, markers, or both.',
        ).widget
        self.mode.setMaximumWidth(200)

        self.line_width = formatting_plot_type.add_int(
            key='scatter.line_width',
            title='Line Width',
            value=self.fig.settings.get('line_width', 1),
            minimum=1,
            maximum=10,
            subtitle='Set the line thickness.',
            description='Adjust the thickness of lines in the plot (if lines are enabled).',
        ).widget
        self.line_width.setMaximumWidth(80)

        self.marker_size = formatting_plot_type.add_int(
            key='scatter.marker_size',
            title='Marker Size',
            value=self.fig.settings.get('marker_size', 6),
            minimum=1,
            maximum=20,
            subtitle='Set the marker size.',
            description='Adjust the size of markers in the plot (if markers are enabled).',
        ).widget
        self.marker_size.setMaximumWidth(80)

    def validate_window(self) -> str | None:
        if not hasattr(self, "_regex_y"):
            return None
        if not self._regex_y.text().strip():
            return "Y Data regex cannot be empty."
        return None
    
    def apply(self) -> None:
        """Apply the current settings to the graph view."""
        
        self.fig.plot.setTitle(self._title.text())
        self.fig.plot.setLabel('bottom', self._x_title.text())
        self.fig.plot.setLabel('left', self._y_title.text())

        grid = self.fig.settings.get('show_grid', {'x': True, 'y': True, 'alpha': 0.3})
        self.fig.plot.showGrid(x=grid.get('x', True), y=grid.get('y', True), alpha=grid.get('alpha', 0.3))
        self.fig.legend.setVisible(bool(self._show_legend.isChecked()))

        x = bool(self._show_grid_x.isChecked())  # Default to True if not specified
        y = bool(self._show_grid_y.isChecked())  # Default to True if not specified
        self.fig.plot.showGrid(x=x, y=y, alpha=0.3)
        
        marker_size = int(self.marker_size.value())
        # Update existing scatter items
        for scatter in self.fig.scatter_items:
            scatter.setSize(marker_size)
        
        mode = self.mode.currentText()
        if mode not in ('lines', 'markers', 'lines+markers'):
            mode = 'markers'
        # Apply mode to existing curves
        for c in self.fig.curves:
            pen = pg.mkPen(c.opts['pen'].color(), width=self.line_width.value()) if ('lines' in mode) else None
            sym = 'o' if ('markers' in mode) else None
            c.setPen(pen)
            c.setSymbol(sym)
            if sym:
                c.setSymbolSize(marker_size)  
            
        line_width = int(self.line_width.value())
        # Update existing curves
        for c in self.fig.curves:
            pen = pg.mkPen(c.opts['pen'].color(), width=line_width) if ('lines' in mode) else None
            c.setPen(pen)
                
        self.fig.regex_x = self._regex_x.text()
        self.fig.regex_y = self._regex_y.text()
        self.fig.set_filter(self._filter.text())
        self.fig.set_group_by(self._group_by.text())
