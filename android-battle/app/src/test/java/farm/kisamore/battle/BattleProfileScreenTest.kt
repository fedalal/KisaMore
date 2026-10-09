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
        // Robolectric can omit software bitmap pixels depending on graphics mode.
        // Assert actual laid-out card dimensions, not a particular pixel color.
        assertTrue("Profile card should have positive height", screen.getChildAt(2).measuredHeight > 0)
        assertTrue("Stats must be laid out", screen.getChildAt(4).measuredHeight > 0)
        assertTrue("Plant card must be laid out", screen.getChildAt(6).measuredHeight > 0)
        assertTrue("Rewards should be visible", screen.getChildAt(8).measuredHeight > 0)
        assertTrue("History should be visible", screen.getChildAt(10).measuredHeight > 0)
        assertTrue("Settings should be visible", screen.getChildAt(12).measuredHeight > 0)
        assertTrue("Settings must fit above bottom navigation", screen.getChildAt(12).bottom <= height)
        // No huge flexible spacers: only a few dp between sections.
        assertTrue("Profile gap is unexpectedly large",
            screen.getChildAt(1).measuredHeight <= 16 * activity.resources.displayMetrics.density)

    }

    @Test
    fun bottomTabGlyphHasSquareDimensions() {
        val activity = Robolectric.buildActivity(Activity::class.java).setup().get()
        val tab = BattleBottomTab(activity, "Профиль", "profile", true) {}
        val icon = tab.getChildAt(0)
        assertEquals(icon.layoutParams.width, icon.layoutParams.height)
        assertTrue(icon.layoutParams.width > 0)
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
