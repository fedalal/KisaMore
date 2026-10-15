package farm.kisamore.battle

import android.app.Activity
import android.graphics.Bitmap
import android.net.Uri
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class RackMediaViewerTest {
    @Test fun zoomStartsAtFitAndSupportsInOutResetAndUpperBound() {
        val activity = Robolectric.buildActivity(Activity::class.java).setup().get()
        val view = ZoomableRackImageView(activity)
        view.layout(0, 0, 390, 640)
        view.displayPhoto(Bitmap.createBitmap(2048, 1536, Bitmap.Config.ARGB_8888))
        assertEquals(1f, view.zoomFactor, 0.001f)
        view.zoomIn()
        assertTrue(view.zoomFactor > 1f)
        view.zoomOut()
        assertEquals(1f, view.zoomFactor, 0.001f)
        repeat(12) { view.zoomIn() }
        assertEquals(6f, view.zoomFactor, 0.001f)
        view.zoomOut()
        assertTrue(view.zoomFactor < 6f)
        view.resetZoom()
        assertEquals(1f, view.zoomFactor, 0.001f)
    }

    @Test fun sourcePhotosCanBeSwappedWithoutRetainingOldZoom() {
        val activity = Robolectric.buildActivity(Activity::class.java).setup().get()
        val view = ZoomableRackImageView(activity)
        view.layout(0, 0, 390, 600)
        view.displayPhoto(Bitmap.createBitmap(1920, 1080, Bitmap.Config.ARGB_8888))
        view.zoomIn()
        assertTrue(view.zoomFactor > 1f)
        view.displayPhoto(Bitmap.createBitmap(2048, 1536, Bitmap.Config.ARGB_8888))
        assertEquals(1f, view.zoomFactor, 0.001f)
    }

    @Test fun timelapseIsCentredAndFitsWithoutCropping() {
        // Portrait phone, landscape MP4: video uses the full width, centred vertically.
        assertEquals(390 to 219, fitRackVideo(1920, 1080, 390, 660))
        // Tall MP4: video uses the available height and stays inside the viewport.
        assertEquals(371 to 660, fitRackVideo(1080, 1920, 390, 660))
        // A 4:3 camera is also fitted rather than clipped.
        assertEquals(390 to 293, fitRackVideo(2048, 1536, 390, 660))
        // Never exceed the viewport, even on very small phones.
        val size = fitRackVideo(3840, 2160, 240, 180)
        assertTrue(size.first <= 240 && size.second <= 180)
        assertEquals(1 to 1, fitRackVideo(0, 0, 390, 660))
    }

    @Test fun shareProviderNeverExportsArbitraryFiles() {
        val provider = Robolectric.buildContentProvider(RackPhotoShareProvider::class.java).create().get()
        val invalid = Uri.parse("content://farm.kisamore.battle.photos/shared/../../private.jpg")
        assertNull(provider.getType(invalid))
        val unrelated = Uri.parse("content://farm.kisamore.battle.photos/config/passwords")
        assertNull(provider.getType(unrelated))
    }
}
