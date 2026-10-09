package farm.kisamore.battle

import android.app.Activity
import android.graphics.Bitmap
import android.graphics.Canvas
import android.view.View
import android.widget.TextView
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [33])
class BattleProfileScreenTest {

    @Test
    fun profileIsPopulatedImmediatelyBeforeAnySizeChange() {
        val activity = Robolectric.buildActivity(Activity::class.java).setup().get()
        val screen = createProfile(activity)
        assertTrue("Profile must not be a blank view", screen.childCount >= 7)
        assertEquals("Профиль", (screen.getChildAt(0) as TextView).text.toString())
        assertTrue("Photo section must exist", screen.getChildAt(2).visibility == View.VISIBLE)
    }

    @Test
    fun profileMeasuresAndDrawsAtPhoneSizeWithoutScroll() {
        val activity = Robolectric.buildActivity(Activity::class.java).setup().get()
        val screen = createProfile(activity)
        val width = (360 * activity.resources.displayMetrics.density).toInt()
        val height = (620 * activity.resources.displayMetrics.density).toInt()
        screen.measure(
            View.MeasureSpec.makeMeasureSpec(width, View.MeasureSpec.EXACTLY),
            View.MeasureSpec.makeMeasureSpec(height, View.MeasureSpec.EXACTLY)
        )
        screen.layout(0, 0, width, height)
        assertEquals(height, screen.measuredHeight)
        val picture = Bitmap.createBitmap(width, height, Bitmap.Config.ARGB_8888)
        screen.draw(Canvas(picture))
        // Card positions change with screen height. Search the entire draw result,
        // not a single pixel that might fall in a flexible spacer.
        val pixels = IntArray(width * height)
        picture.getPixels(pixels, 0, width, 0, 0, width, height)
        val whitePixels = pixels.count { it == android.graphics.Color.WHITE }
        assertTrue("Expected visible white cards, found $whitePixels white pixels", whitePixels > 10)
    }

    private fun createProfile(activity: Activity) = BattleProfileScreen(
        activity,
        null,
        GameProfile(0, 1, 0, emptyList(), emptyList()),
        emptyList(),
        null,
        onChangePhoto = {},
        onLogin = {},
        onPlant = {},
        onHistory = {},
        onRegion = {},
        onLogout = {}
    )
}
