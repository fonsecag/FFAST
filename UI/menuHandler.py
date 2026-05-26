import os
import sys
from events import EventClass
from PySide6.QtWidgets import QFileDialog
from UI.Templates import customFileDialog, BigDatasetWarningDialog
from collections.abc import Mapping, Container
from client.dataType import AtomsList


def deep_getsizeof(obj, seen=None):
    """
    Function to calculate the size of an object on memory in bites.
    :param obj: Desired object
    :param seen: Flag to avoid double counting of objects.
    :return: Size of the object in bytes.
    """
    if seen is None:
        seen = set()

    obj_id = id(obj)
    if obj_id in seen:
        return 0
    seen.add(obj_id)

    size = sys.getsizeof(obj)

    if isinstance(obj, Mapping):
        size += sum(deep_getsizeof(k, seen) + deep_getsizeof(v, seen) for k, v in obj.items())
    elif isinstance(obj, (list, tuple, set, frozenset)):
        size += sum(deep_getsizeof(i, seen) for i in obj)
    elif hasattr(obj, "__dict__"):
        size += deep_getsizeof(obj.__dict__, seen)
    elif hasattr(obj, "__slots__"):
        for slot in obj.__slots__:
            if hasattr(obj, slot):
                size += deep_getsizeof(getattr(obj, slot), seen)

    return size


class MenuHandler(EventClass):
    def __init__(self, window, mode="main"):
        self.handler = window.handler
        self.window = window
        self.mode = mode  # either "main" for the main window or "loupe" for loupes.
        self.connectActions()

    def connectActions(self):
        handler, window = (self.handler, self.window)
        mb = window.menuBar()
        if self.mode == 'main':
            # FILE
            File = mb.addMenu("&File")
            File.addAction("Save", self.onSave, "Ctrl+s")
            File.addAction("Load", self.onLoad, "Ctrl+l")

            File.addAction("Load Dataset", self.onDatasetLoad, "Ctrl+d")
            File.addAction("Load Model", self.onModelLoad, "Ctrl+m")

            File.addAction("Load Zero Model", self.onZeroModelLoad, "Ctrl+0")
            File.addAction("Load Prediction", self.onPrepredictedModelLoad, "Ctrl+p")

            File.addSeparator()
            File.addAction(
                "Connect to Cluster…",
                self.onConnectToCluster,
                "Ctrl+Shift+C",
            )

            # File.addAction("Preferences", self.onPreferences)
            # File.addAction("Exit", self.onExit)

        # LOUPE
        Loupe = mb.addMenu("&3D &View")
        Loupe.addAction("New", self.newLoupe, "Ctrl+n")
        Loupe.addSeparator()
        if self.mode == "loupe":
            # Bond Width submenu
            bondMenu = Loupe.addMenu("Bond Width")
            bondMenu.addAction("Thin (10)", lambda: self.setBondWidth(10))
            bondMenu.addAction("Normal (25)", lambda: self.setBondWidth(25))
            bondMenu.addAction("Thick (50)", lambda: self.setBondWidth(50))
            bondMenu.addAction("Extra Thick (100)", lambda: self.setBondWidth(100))
            # TODO: add custom bond width dialog
            # bondMenu.addSeparator()
            # bondMenu.addAction("Custom...", self.showBondWidthDialog)

            # Atom Size submenu
            atomMenu = Loupe.addMenu("Atom Size")
            atomMenu.addAction("50%", lambda: self.setAtomSize(0.5))
            atomMenu.addAction("75%", lambda: self.setAtomSize(0.75))
            atomMenu.addAction("100%", lambda: self.setAtomSize(1.0))
            atomMenu.addAction("150%", lambda: self.setAtomSize(1.5))
            atomMenu.addAction("200%", lambda: self.setAtomSize(2.0))
            # TODO: add custom atom size dialog
            # atomMenu.addSeparator()
            # atomMenu.addAction("Custom...", self.showAtomSizeDialog)

            # Colors submenu
            colorMenu = Loupe.addMenu("Colors")
            colorMenu.addAction("Bond Color...", self.showBondColorPicker)
            colorMenu.addAction("Background Color...", self.showBackgroundColorPicker)

    def onSave(self):
        workdir = self.handler.workdir
        (path, _) = QFileDialog.getSaveFileName(self.handler.window, "Save File", workdir)
        if path is None or path.strip() == "":
            return

        self.handler.env.newTask(
            self.handler.env.save,
            args=(path,),
            visual=True,
            name=f"Saving at {os.path.basename(path)}",
            threaded=True,
        )

    def onLoad(self):
        workdir = self.handler.workdir
        path = QFileDialog.getExistingDirectory(self.handler.window, "Select Directory", workdir)
        if path is None or path.strip() == "":
            return

        self.handler.env.newTask(
            self.handler.env.load,
            args=(path,),
            visual=True,
            name=f"Loading {os.path.basename(path)}",
            threaded=True,
        )

    def onPreferences(self):
        pass

    def onExit(self):
        self.eventPush("QUIT_EVENT")

    def onDatasetLoad(self):
        import logging
        logger = logging.getLogger("FFAST")

        env = self.handler.env
        workdir = self.handler.workdir
        fileTypes = sorted(list(env.datasetTypes.keys()))
        extensions = [
            env.datasetTypes[x].datasetFileExtension for x in fileTypes
        ]
        path, typ = customFileDialog(
            self.handler.window, fileTypes=fileTypes, extensions=extensions, directory=workdir
        )
        if path is None:
            logger.warning("No path was selected, please try again later")
            return
        # For ASE datasets, show key selection dialog on main thread (before threaded task)
        selected_energy_key = None
        selected_force_key = None
        prediction_keys = None

        if typ == "ase (auto)" and path:
            # Show dialog on main thread to avoid Qt threading issues
            result = self._showASEKeySelectionDialog(path)

            # If user cancelled, abort (all three values are None)
            if result == (None, None, None):
                return

            selected_energy_key, selected_force_key, prediction_keys = result
        file_size = os.path.getsize(path) / 1_000_000_000
        slice_num = -1  # load entirely on RAM by default
        if file_size >= 3:
            slice_num = self.large_dataset_handle(path, logger)

        if slice_num == -2:
            logger.info("load cancelled.")
            return
        if slice_num > 0:
            logger.info(f"loading dataset with slice: {slice_num}")
        env.taskLoadDataset(path, typ, selected_energy_key=selected_energy_key, selected_force_key=selected_force_key,
                            prediction_keys=prediction_keys, slice_num=slice_num)

    def large_dataset_handle(self, path, logger):
        from PySide6.QtWidgets import QDialog
        import ase.io

        logger.info("Large dataset detected, calculating the length.")
        length = AtomsList.calc_dataset_length_static(path)
        logger.info(f"Total dataset length: {length}")

        logger.info("Total length calculated, approximating size of each atom in dataset.")
        temp_dataset = ase.io.read(path, index=slice(0, 1000, None))
        temp_size = deep_getsizeof(temp_dataset)  # the size of temp_dataset in bytes.
        avg_per_atom_size = temp_size/1000
        file_size = length*avg_per_atom_size
        logger.info(f"Total size of the dataset on RAM would be approximately {file_size/1_000_000_000:.2f} GBs.")

        dialog = BigDatasetWarningDialog(file_size, length, self.handler.window)
        result = dialog.exec()
        if result == QDialog.Accepted:
            slice_num = dialog.get_slice_number()
            if dialog.user_clicked_pick_samples:
                try:
                    slice_num = int(slice_num)
                    if slice_num >= 0:
                        return slice_num
                    else:
                        logger.info("Invalid slice number entered, load abort.")
                        return -2
                except (ValueError, TypeError):
                    logger.info("Invalid slice number entered, load abort.")
                    return -2
            elif dialog.user_clicked_load_no_cache:
                logger.info("User decided to load the whole dataset without caching.")
                return -1
            else:
                logger.info("User decided to load the whole dataset with caching.")
                return 0
        else:
            logger.info("User cancelled the load operation.")
            return -2



    def _showASEKeySelectionDialog(self, path, for_predictions=False):
        """Show ASE key selection dialog on main thread.

        Reads only the FIRST frame to detect available keys, then shows dialog.
        The full dataset is loaded later in the background thread.

        Args:
            path: Path to the ASE file
            for_predictions: If True, show simplified dialog for loading predictions only

        Returns:
            tuple: (selected_energy_key, selected_force_key, prediction_keys) or (None, None, None) if cancelled
        """
        import ase.io
        from modules.aseDataset import aseDatasetLoader
        from UI.KeySelectionDialog import KeySelectionDialog
        import logging

        logger = logging.getLogger("FFAST")

        try:
            # Read ONLY first frame to detect keys (much faster for large datasets)
            first_atoms = ase.io.read(path, index=0)

            # Create temporary loader with just first frame to access key detection
            # We'll load the full dataset later in the background thread
            temp_loader = aseDatasetLoader(path, atomsList=[first_atoms])

            # Check if multiple keys exist
            energy_keys = temp_loader.EneregyKeys()
            force_keys = temp_loader.ForceKeys()

            # Check if calculator is available
            has_calculator_energy = False
            has_calculator_forces = False
            try:
                first_atoms.get_potential_energy()
                has_calculator_energy = True
            except:
                pass

            try:
                first_atoms.get_forces()
                has_calculator_forces = True
            except:
                pass

            logger.info(f"Detected {len(energy_keys)} energy key(s) and {len(force_keys)} force key(s) from first frame")
            logger.info(f"Calculator available: energy={has_calculator_energy}, forces={has_calculator_forces}")

            # Count total options for each
            energy_options = len(energy_keys) + (1 if has_calculator_energy else 0)
            force_options = len(force_keys) + (1 if has_calculator_forces else 0)

            # Skip dialog only if there's exactly one option for each
            if energy_options <= 1 and force_options <= 1:
                # Use the single available option for each
                selected_energy = energy_keys[0] if energy_keys else (None if has_calculator_energy else None)
                selected_force = force_keys[0] if force_keys else (None if has_calculator_forces else None)
                return (selected_energy, selected_force, [])

            # Show dialog
            dialog = KeySelectionDialog(
                energy_keys, force_keys,
                parent=self.handler.window,
                for_predictions=for_predictions
            )
            if dialog.exec() == KeySelectionDialog.Accepted:
                selection = dialog.getSelection()
                return (
                    selection['energy_ref'],
                    selection['force_ref'],
                    selection['predictions']
                )
            else:
                # User cancelled
                logger.info("Dataset loading cancelled by user")
                return None, None, None

        except Exception as e:
            logger.error(f"Unable to read file: {path}. Error showing ASE key selection dialog: {e}")
            logger.error(f"The ase dataset loader could not recognize the specified dataset:"
                         f"'{path}'.\nIf you are choosing a file with .npz extension, please try again "
                         f"and choose *.npz in the file type filter dropdown")
            return None, None, None  # was Nona, Nona, []. (coding bug)

    def onModelLoad(self):
        env = self.handler.env
        workdir = self.handler.workdir
        fileTypes = list(env.modelTypes.keys())
        extensions = [env.modelTypes[x].modelFileExtension for x in fileTypes]
        path, typ = customFileDialog(
            self.handler.window, fileTypes=fileTypes, extensions=extensions, directory=workdir
        )

        env.taskLoadModel(path, typ)

    def onPrepredictedModelLoad(self):
        import logging
        logger = logging.getLogger("FFAST")

        env = self.handler.env
        workdir = self.handler.workdir
        names = [x.getName() for x in env.getAllDatasets(excludeSubs=True)]
        keys = [x.fingerprint for x in env.getAllDatasets(excludeSubs=True)]
        extensions = ["*"] * len(names)
        extensions += ["*.npz"] * len(names)
        names += names
        path, typ = customFileDialog(
            self.handler.window, fileTypes=names, extensions=extensions, directory=workdir
        )

        if path is None:
            logger.warning("No path was selected please try again.")
            return

        idx = names.index(typ)
        # For ASE files (non-NPZ), show key selection dialog on main thread
        selected_energy_key = None
        selected_force_key = None

        if path and "npz" not in path:
            # ASE file - might have multiple keys
            result = self._showASEKeySelectionDialog(path, for_predictions=True)

            # If user cancelled, abort
            if result == (None, None, None):
                return

            selected_energy_key, selected_force_key, _ = result  # Ignore prediction_keys for this use case

        env.taskLoadPrepredictedDataset(
            path, keys[idx],
            selected_energy_key=selected_energy_key,
            selected_force_key=selected_force_key
        )

    def newLoupe(self):
        self.handler.newLoupe()

    def onZeroModelLoad(self):
        env = self.handler.env
        env.taskLoadZeroModel()

    def setBondWidth(self, width):
        """Set bond width for the current Loupe."""
        loupe = self.window
        if not loupe:
            return
        loupe.settings.setParameter("bondWidth", width, refresh=True)

    def setAtomSize(self, scale):
        """Set atom size scale for the current Loupe."""
        loupe = self.window
        if loupe and hasattr(loupe, 'settings'):
            loupe.settings.setParameter("atomSizeScale", scale, refresh=True)

    def showBondWidthDialog(self):
        """Show custom bond width input dialog (current loupe)."""
        loupe = self.window
        if not loupe:
            return

        from PySide6.QtWidgets import QInputDialog
        current = loupe.settings.get("bondWidth", 200)
        value, ok = QInputDialog.getInt(
            self.window,
            "Bond Width",
            "Enter bond width (pixels):",
            value=current,
            min=10,
            max=1000,
            step=10
        )
        if ok:
            self.setBondWidth(value)

    def showAtomSizeDialog(self):
        """Show custom atom size input dialog. (current loupe)"""
        loupe = self.window
        if not loupe:
            return

        from PySide6.QtWidgets import QInputDialog
        current = loupe.settings.get("atomSizeScale", 1.0)
        value, ok = QInputDialog.getDouble(
            self.window,
            "Atom Size",
            "Enter atom size scale:",
            value=current,
            min=0.1,
            max=10.0,
            decimals=2
        )
        if ok:
            self.setAtomSize(value)

    def showBondColorPicker(self):
        """Show bond color picker dialog. (current loupe)"""
        loupe = self.window
        if not loupe:
            return

        from PySide6.QtWidgets import QColorDialog
        from PySide6.QtGui import QColor
        from config.userConfig import getConfig

        current_hex = loupe.settings.get("bondColor", getConfig("loupeBondsColor", "#404040"))
        current_color = QColor(current_hex)

        color = QColorDialog.getColor(
            current_color,
            self.window,
            "Select Bond Color"
        )

        if color.isValid():
            hex_color = color.name()
            loupe.settings.setParameter("bondColor", hex_color, refresh=True)

    def showBackgroundColorPicker(self):
        """Show background color picker dialog. (current loupe)"""
        loupe = self.window
        if not loupe:
            return

        from PySide6.QtWidgets import QColorDialog
        from PySide6.QtGui import QColor
        from config.userConfig import getConfig

        current_hex = getConfig("loupeBGColor", "#000000")
        current_color = QColor(current_hex)

        color = QColorDialog.getColor(
            current_color,
            self.window,
            "Select Background Color"
        )

        if color.isValid():
            # Update canvas background directly
            loupe.canvas.canvas.bgcolor = color.getRgbF()[:3]
            loupe.canvas.canvas.update()

    def onConnectToCluster(self):
        """Open the cluster connection dialog."""
        from UI.ClusterProfileDialog import ClusterConnectDialog

        dialog = ClusterConnectDialog(parent=self.handler.window)
        if dialog.exec() == ClusterConnectDialog.Accepted:
            profile = dialog.get_profile()
            logger.info(
                "Connect requested: host=%s user=%s partition=%s",
                profile.host,
                profile.username,
                profile.partition,
            )
            # TODO: initiate SSH tunnel + job submission using profile
