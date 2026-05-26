import numpy as np
import logging
import os
from functools import partial

logger = logging.getLogger("FFAST")
DEPENDENCIES = ["loupeCamera"]


def exportImagePIL(loupe, transparent=False, format="png"):
    """Export using PIL/Pillow (supports quality control and transparency).

    Args:
        loupe: The Loupe instance
        transparent: If True, use transparent background (PNG only)
        format: Image format ('png' or 'jpg')
    """
    try:
        from PIL import Image
    except ImportError:
        logger.error("PIL/Pillow not installed. Run: pip install pillow")
        return

    canvas = loupe.canvas.canvas
    settings = loupe.settings

    # Get export settings
    # jpeg_quality = int(settings.get("exportJPEGQuality"))

    # Get file path from user
    filter_str = "PNG Files (*.png)" #if format == "png" else "JPEG Files (*.jpg *.jpeg)"
    default_ext = ".png" #if format == "png" else ".jpg"
    workdir = loupe.handler.workdir
    dataset_name = loupe.canvas.dataset.getName()
    default_filename = os.path.join(workdir, f"{dataset_name}_frame_{loupe.index}{default_ext}")

    from PySide6.QtWidgets import QFileDialog

    file_path, _ = QFileDialog.getSaveFileName(
        loupe,
        "Save Image (PIL)",
        default_filename,
        filter_str
    )

    if not file_path:
        return  # User cancelled

    # Save original size and background
    original_size = canvas.size
    original_bgcolor = canvas.bgcolor

    try:
        # Scale canvas size if needed
        # if scale_factor > 1:
        #     new_size = (original_size[0] * scale_factor, original_size[1] * scale_factor)
        #     canvas.size = new_size
        #     canvas.update()

        # Set background color based on export type
        if transparent and format == "png":
            # For transparent exports, render with black background then make it transparent
            # (workaround for Vispy Line visuals not rendering with transparent bgcolor)
            canvas.bgcolor = (0, 0, 0, 1)  # Black opaque background
            canvas.update()
        else:
            # For opaque exports, use the selected background color
            bg_rgb = settings.get("exportBackgroundColor")
            canvas.bgcolor = (bg_rgb[0] / 255.0, bg_rgb[1] / 255.0, bg_rgb[2] / 255.0, 1)
            canvas.update()

        # Force complete geometry update to regenerate all properties and visuals
        loupe.canvas.onNewGeometry()

        # Additional update to ensure canvas processes all changes
        canvas.update()

        # Process pending events to ensure all updates are applied
        from PySide6.QtWidgets import QApplication
        QApplication.processEvents()

        # Do a priming render to ensure graphics pipeline is ready
        _ = canvas.render()

        # Final render for export
        img_array = canvas.render()

        # Convert to PIL Image and make background transparent if requested
        if transparent and format == "png":
            # Start with RGBA mode
            img = Image.fromarray(img_array, mode='RGBA')

            # Convert to numpy array for processing
            img_data = np.array(img)

            # Make black pixels (background) transparent
            # Black is (0, 0, 0) with some tolerance for antialiasing
            black_pixels = (img_data[:, :, 0] < 5) & (img_data[:, :, 1] < 5) & (img_data[:, :, 2] < 5)
            img_data[black_pixels, 3] = 0  # Set alpha to 0 for black pixels

            # Convert back to PIL Image
            img = Image.fromarray(img_data, mode='RGBA')
        else:
            img = Image.fromarray(img_array[:, :, :3], mode='RGB')

        # Save the image
        # if format == "png":
        img.save(file_path, format='PNG', compress_level=6)  # No compression for max quality
        # else:
            # img.save(file_path, format='JPEG', quality=jpeg_quality)

        logger.info(f"Image saved (PIL) to: {file_path} [Size: {img.size}, Quality: 'N/A']")#{jpeg_quality if format=='jpg' else

    finally:
        # Restore original size and background
        canvas.size = original_size
        canvas.bgcolor = original_bgcolor
        canvas.update()
        # Restore visual elements
        loupe.canvas.visualRefresh(force=True)


# def exportImageVispy(loupe, transparent=False):
    # """Export using native Vispy method.

    # Args:
    #     loupe: The Loupe instance
    #     transparent: If True, use transparent background
    # """
    # import vispy.io as io

    # canvas = loupe.canvas.canvas
    # settings = loupe.settings

    # # Get file path from user
    # workdir = loupe.handler.workdir
    # dataset_name = loupe.canvas.dataset.getName()
    # default_filename = os.path.join(workdir, f"{dataset_name}_frame_{loupe.index}.png")

    # file_path, _ = QFileDialog.getSaveFileName(
    #     loupe,
    #     "Save Image (Vispy Native)",
    #     default_filename,
    #     "PNG Files (*.png)"
    # )

    # if not file_path:
    #     return  # User cancelled

    # # Save original size and background
    # original_size = canvas.size
    # original_bgcolor = canvas.bgcolor

    # try:
    #     # Scale canvas size if needed
    #     # if scale_factor > 1:
    #     #     new_size = (original_size[0] * scale_factor, original_size[1] * scale_factor)
    #     #     canvas.size = new_size
    #     #     canvas.update()

    #     # Set background color based on export type
    #     if transparent:
    #         # For transparent exports, render with black background then make it transparent
    #         # (workaround for Vispy Line visuals not rendering with transparent bgcolor)
    #         canvas.bgcolor = (0, 0, 0, 1)  # Black opaque background
    #         canvas.update()
    #     else:
    #         # For opaque exports, use the selected background color
    #         bg_rgb = settings.get("exportBackgroundColor")
    #         canvas.bgcolor = (bg_rgb[0] / 255.0, bg_rgb[1] / 255.0, bg_rgb[2] / 255.0, 1)
    #         canvas.update()

    #     # Force complete geometry update to regenerate all properties and visuals
    #     loupe.canvas.onNewGeometry()

    #     # Additional update to ensure canvas processes all changes
    #     canvas.update()

    #     # Process pending events to ensure all updates are applied
    #     from PySide6.QtWidgets import QApplication
    #     QApplication.processEvents()

    #     # Do a priming render to ensure graphics pipeline is ready
    #     _ = canvas.render()

    #     # Final render for export
    #     img_array = canvas.render()

    #     # Make background transparent if requested
    #     if transparent:
    #         # Make black pixels (background) transparent
    #         # Black is (0, 0, 0) with some tolerance for antialiasing
    #         black_pixels = (img_array[:, :, 0] < 5) & (img_array[:, :, 1] < 5) & (img_array[:, :, 2] < 5)
    #         img_array[black_pixels, 3] = 0  # Set alpha to 0 for black pixels

    #     io.write_png(file_path, img_array)

    #     logger.info(f"Image saved (Vispy) to: {file_path} [Size: {canvas.size}]")

    # finally:
    #     # Restore original size and background
    #     canvas.size = original_size
    #     canvas.bgcolor = original_bgcolor
    #     canvas.update()
    #     # Restore visual elements
    #     loupe.canvas.visualRefresh(force=True)


# PIL Export functions
def exportImagePILOpaque(loupe):
    """Export using PIL with opaque background."""
    exportImagePIL(loupe, transparent=False, format="png")


def exportImagePILTransparent(loupe):
    """Export using PIL with transparent background."""
    exportImagePIL(loupe, transparent=True, format="png")


# def exportImagePILJPEG(loupe):
#     """Export using PIL as JPEG."""
#     exportImagePIL(loupe, transparent=False, format="jpg")


# # Vispy Export functions
# def exportImageVispyOpaque(loupe):
#     """Export using Vispy with opaque background."""
#     exportImageVispy(loupe, transparent=False)


# def exportImageVispyTransparent(loupe):
#     """Export using Vispy with transparent background."""
#     exportImageVispy(loupe, transparent=True)


def addSettings(UIHandler, loupe):
    """Add export settings to loupe."""
    settings = loupe.settings
    settings.addParameters(**{
        # "exportJPEGQuality": [95, None],  # JPEG quality (1-100)
        "exportBackgroundColor": [(255, 255, 255), None],  # Background color for opaque exports (RGB tuple)
    })


def addSettingsPane(UIHandler, loupe):
    """Add export controls to the Loupe sidebar."""
    from UI.Templates import SettingsPane, PushButton, Widget
    from PySide6.QtWidgets import QLabel, QColorDialog
    from PySide6.QtGui import QColor

    pane = SettingsPane(UIHandler, loupe.settings, parent=loupe)

    # Quality/Resolution Settings
    # pane.addSetting(
    #     "ComboBox",
    #     "Scale Factor",
    #     items=["1", "2", "3", "4"],
    #     toolTip="Resolution multiplier (higher = larger image, better quality)",
    # )

    # pane.addSetting(
    #     "LineEdit",
    #     "JPEG Quality",
    #     settingsKey="exportJPEGQuality",
    #     isInt=True,
    #     nMin=1,
    #     nMax=100,
    #     toolTip="JPEG compression quality (1-100, higher = better quality)",
    # )

    # Background Color Picker
    colorContainer = Widget(parent=pane, layout="horizontal")
    colorLabel = QLabel("Background Color:", parent=colorContainer)
    colorContainer.layout.addWidget(colorLabel)

    colorButton = PushButton("Choose Color", parent=colorContainer)
    colorButton.setToolTip("Select background color for opaque PNG export") #and JPEG

    def updateButtonColor():
        """Update button style to show current color."""
        rgb = loupe.settings.get("exportBackgroundColor")
        colorButton.setStyleSheet(f"background-color: rgb({rgb[0]}, {rgb[1]}, {rgb[2]}); color: {'black' if sum(rgb) > 384 else 'white'};")

    def pickColor():
        """Open color picker dialog."""
        current_rgb = loupe.settings.get("exportBackgroundColor")
        current_color = QColor(current_rgb[0], current_rgb[1], current_rgb[2])

        color = QColorDialog.getColor(current_color, loupe, "Select Background Color")
        if color.isValid():
            new_rgb = (color.red(), color.green(), color.blue())
            loupe.settings.setParameter("exportBackgroundColor", new_rgb, refresh=False)
            updateButtonColor()

    colorButton.clicked.connect(pickColor)
    updateButtonColor()  # Set initial color
    colorContainer.layout.addWidget(colorButton)

    pane.layout.addWidget(colorContainer)

    # Add separator
    separator1 = QLabel("─" * 30, parent=pane)
    pane.layout.addWidget(separator1)

    # PIL Export Section
    pilLabel = QLabel("PIL/Pillow Export:", parent=pane)
    pilLabel.setStyleSheet("font-weight: bold;")
    pane.layout.addWidget(pilLabel)

    buttonContainerPIL = Widget(parent=pane, layout="vertical")

    pngOpaqueBtnPIL = PushButton("PNG (Opaque)", parent=buttonContainerPIL)
    pngOpaqueBtnPIL.setToolTip("Save as PNG with current background using PIL")
    pngOpaqueBtnPIL.clicked.connect(partial(exportImagePILOpaque, loupe))
    buttonContainerPIL.layout.addWidget(pngOpaqueBtnPIL)

    pngTransparentBtnPIL = PushButton("PNG (Transparent)", parent=buttonContainerPIL)
    pngTransparentBtnPIL.setToolTip("Save as PNG with transparent background using PIL")
    pngTransparentBtnPIL.clicked.connect(partial(exportImagePILTransparent, loupe))
    buttonContainerPIL.layout.addWidget(pngTransparentBtnPIL)

    # jpegBtnPIL = PushButton("JPEG")
    # jpegBtnPIL.setToolTip("Save as JPEG using PIL (quality controlled)")
    # jpegBtnPIL.clicked.connect(partial(exportImagePILJPEG, loupe))
    # buttonContainerPIL.layout.addWidget(jpegBtnPIL)

    pane.layout.addWidget(buttonContainerPIL)

    # Add separator
    separator2 = QLabel("─" * 30, parent=pane)
    pane.layout.addWidget(separator2)

    # Vispy Export Section
    vispyLabel = QLabel("Vispy Native Export:", parent=pane)
    vispyLabel.setStyleSheet("font-weight: bold;")
    pane.layout.addWidget(vispyLabel)

    # buttonContainerVispy = Widget(parent=pane, layout="vertical")

    # pngOpaqueBtnVispy = PushButton("PNG (Opaque)")
    # pngOpaqueBtnVispy.setToolTip("Save as PNG with current background using native Vispy")
    # pngOpaqueBtnVispy.clicked.connect(partial(exportImageVispyOpaque, loupe))
    # buttonContainerVispy.layout.addWidget(pngOpaqueBtnVispy)

    # pngTransparentBtnVispy = PushButton("PNG (Transparent)")
    # pngTransparentBtnVispy.setToolTip("Save as PNG with transparent background using native Vispy")
    # pngTransparentBtnVispy.clicked.connect(partial(exportImageVispyTransparent, loupe))
    # buttonContainerVispy.layout.addWidget(pngTransparentBtnVispy)

    # pane.layout.addWidget(buttonContainerVispy)

    loupe.addSidebarPane("EXPORT", pane)


def loadLoupe(UIHandler, loupe):
    """Main entry point for loading the export module."""
    addSettings(UIHandler, loupe)
    addSettingsPane(UIHandler, loupe)
