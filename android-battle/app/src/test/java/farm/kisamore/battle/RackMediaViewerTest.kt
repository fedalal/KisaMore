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

    @Test fun shareProviderNeverExportsArbitraryFiles() {
        val provider = Robolectric.buildContentProvider(RackPhotoShareProvider::class.java).create().get()
        val invalid = Uri.parse("content://farm.kisamore.battle.photos/shared/../../private.jpg")
        assertNull(provider.getType(invalid))
        val unrelated = Uri.parse("content://farm.kisamore.battle.photos/config/passwords")
        assertNull(provider.getType(unrelated))
    }
}
