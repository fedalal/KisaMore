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
        assertEquals("Exactly 5 cards and 4 compact gaps", 9, screen.childCount)
        assertTrue("No redundant title", !containsLabel(screen, "Профиль"))
        assertTrue("Empty rewards clearly labeled", containsLabel(screen, "Наград пока нет"))
        assertTrue("Redundant My Plants block has been removed", !containsLabel(screen, "Мои растения"))
        assertTrue("Help setting exists", containsLabel(screen, "Помощь"))
        assertTrue("Review shortcut exists", containsLabel(screen, "Оценить приложение"))
        assertTrue("Invite shortcut exists", containsLabel(screen, "Пригласить друга"))
        assertTrue("Server setting removed", !containsLabel(screen, "Сервер"))
        assertTrue("Photo section must exist", screen.getChildAt(0).visibility == View.VISIBLE)
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
        assertTrue("Profile card should have positive height", screen.getChildAt(0).measuredHeight > 0)
        assertTrue("Stats must be laid out", screen.getChildAt(2).measuredHeight > 0)
        assertTrue("Rewards card follows stats without a plant card", screen.getChildAt(4).measuredHeight > 0)
        assertTrue("History should be visible", screen.getChildAt(6).measuredHeight > 0)
        assertTrue("Settings should be visible", screen.getChildAt(8).measuredHeight > 0)
        assertTrue("Settings must fit above bottom navigation", screen.getChildAt(8).bottom <= height)
        assertTrue("Natural-height rewards card should remain compact",
            screen.getChildAt(4).measuredHeight <= 100 * activity.resources.displayMetrics.density)
        assertTrue("Natural-height history card should remain compact",
            screen.getChildAt(6).measuredHeight <= 105 * activity.resources.displayMetrics.density)
        val settings = screen.getChildAt(8) as android.view.ViewGroup
        assertTrue("Last settings row must fit within the card",
            settings.getChildAt(settings.childCount - 1).bottom <= settings.height)
        val extraActions = settings.getChildAt(settings.childCount - 1) as android.view.ViewGroup
        assertEquals("Rate and share each have their own full-width row", 2, extraActions.childCount)
        val rate = extraActions.getChildAt(0)
        val invite = extraActions.getChildAt(1)
        assertTrue("Invite must appear below rate", invite.top > rate.top)
        assertEquals("Both actions share the same width", rate.measuredWidth, invite.measuredWidth)
        assertTrue("Tap targets remain at least 43dp on compact screens",
            rate.measuredHeight >= 43 * activity.resources.displayMetrics.density - 1)

        val notificationLabel = findLabel(settings, "Уведомления")
        assertTrue("Settings labels should be at least 14sp",
            notificationLabel.textSize / activity.resources.displayMetrics.scaledDensity >= 13.8f)
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

    private fun containsLabel(view: View, label: String): Boolean =
        runCatching { findLabel(view, label) }.isSuccess

    private fun findLabel(view: View, label: String): TextView {
        if (view is TextView && view.text.toString() == label) return view
        if (view is android.view.ViewGroup) {
            for (index in 0 until view.childCount) {
                val found = runCatching { findLabel(view.getChildAt(index), label) }.getOrNull()
                if (found != null) return found
            }
        }
        throw IllegalArgumentException("Label missing: " + label)
    }

    private fun createProfile(activity: Activity): BattleProfileScreen {
        // Older test expectations explicitly concern the Russian interface.
        // Do not rely on Robolectric's device locale.
        AppLanguage.set(activity, "ru")
        return BattleProfileScreen(
        activity,
        null,
        GameProfile(0, 1, 0, emptyList(), emptyList()),
        emptyList(),
        null,
        onChangePhoto = {},
        onLogin = {},
        onHistory = {},
        onRegion = {},
        onLogout = {}
        )
    }
}
