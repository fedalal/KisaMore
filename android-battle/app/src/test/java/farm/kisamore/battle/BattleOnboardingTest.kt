package farm.kisamore.battle

import android.app.Activity
import android.graphics.Bitmap
import android.graphics.Canvas
import android.view.View
import org.junit.Assert.assertFalse
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [33])
class BattleOnboardingTest {
    @Test
    fun onboardingCompletionSurvivesRecreation() {
        val first = Robolectric.buildActivity(Activity::class.java).setup().get()
        first.getSharedPreferences("kisamore_battle_onboarding", 0)
            .edit().clear().commit()
        assertTrue(BattleOnboarding.shouldShow(first))
        BattleOnboarding.markFinished(first)
        assertFalse(BattleOnboarding.shouldShow(first))

        val second = Robolectric.buildActivity(Activity::class.java).setup().get()
        assertFalse(BattleOnboarding.shouldShow(second))
    }

    @Test
    fun allKeyPagesHaveLocalizedTitlesAndActions() {
        val activity = Robolectric.buildActivity(Activity::class.java).setup().get()
        val keys = listOf(
            "Вы выращиваете настоящее растение",
            "Следите за ростом вживую",
            "Ресурсы ограничены — стратегия важна",
            "Побеждайте и получайте награды",
            "Начать", "Далее", "Назад", "Оценить приложение", "Пригласить друга",
            "Начало и вкладки", "Битва: фото и камеры", "Просмотр фотографии",
            "Мои ресурсы", "Действия и участники", "Профиль и история",
            "К1 / К2 слева", "24 ч / 3 дня / Всё справа",
            "− / По размеру / +", "Фото / ▶ 24 ч / ▶ 3 дня / ▶ Всё",
            "Остаток / лимит", "Активность: 24 ч / 3 дня / 7 дней",
            "Название битвы сверху", "Нижнее меню", "Занять место"
        )
        for (code in listOf("en", "ru", "zh", "de", "fr", "es", "it", "pt", "pl")) {
            AppLanguage.set(activity, code)
            val language = AppLanguage(activity)
            keys.forEach { key ->
                val translated = language.t(key)
                assertTrue("Missing translation $code: $key", translated.isNotBlank())
                if (code != "ru") assertTrue("Untranslated $code: $key", translated != key)
            }
        }
    }

    @Test
    fun artworkMeasuresAndDrawsForAllStepsOnCompactPhones() {
        val activity = Robolectric.buildActivity(Activity::class.java).setup().get()
        for (step in 0..5) {
            val view = BattleOnboardingArtwork(activity, step)
            val width = (300 * activity.resources.displayMetrics.density).toInt()
            val height = (215 * activity.resources.displayMetrics.density).toInt()
            view.measure(View.MeasureSpec.makeMeasureSpec(width, View.MeasureSpec.EXACTLY),
                View.MeasureSpec.makeMeasureSpec(height, View.MeasureSpec.EXACTLY))
            view.layout(0, 0, width, height)
            assertTrue(view.measuredWidth > 0)
            val bitmap = Bitmap.createBitmap(width, height, Bitmap.Config.ARGB_8888)
            view.draw(Canvas(bitmap))
            assertNotNull(bitmap)
            view.measure(View.MeasureSpec.makeMeasureSpec(width, View.MeasureSpec.EXACTLY),
                View.MeasureSpec.makeMeasureSpec(72, View.MeasureSpec.EXACTLY))
            view.layout(0, 0, width, 72)
            view.draw(Canvas(Bitmap.createBitmap(width, 72, Bitmap.Config.ARGB_8888)))
        }
    }
    @Test
    fun horizontalSwipesNavigateBothWaysButVerticalDragsDoNot() {
        assertEquals(1, onboardingSwipeDelta(-145f, 12f, 60f))
        assertEquals(-1, onboardingSwipeDelta(145f, 12f, 60f))
        assertEquals(0, onboardingSwipeDelta(-40f, 2f, 60f))
        assertEquals(0, onboardingSwipeDelta(-100f, 115f, 60f))
    }

    @Test
    fun realSwipeFrameInterceptsHorizontalGestureOnly() {
        val activity = Robolectric.buildActivity(Activity::class.java).setup().get()
        var last = 0
        val frame = OnboardingSwipeFrame(activity) { last = it }
        frame.addView(View(activity).apply { isClickable = true },
            android.widget.FrameLayout.LayoutParams(-1, -1))
        frame.measure(View.MeasureSpec.makeMeasureSpec(360, View.MeasureSpec.EXACTLY),
            View.MeasureSpec.makeMeasureSpec(640, View.MeasureSpec.EXACTLY))
        frame.layout(0, 0, 360, 640)
        fun event(action: Int, x: Float, y: Float) =
            android.view.MotionEvent.obtain(0L, 100L, action, x, y, 0)
        frame.dispatchTouchEvent(event(android.view.MotionEvent.ACTION_DOWN, 250f, 160f))
        frame.dispatchTouchEvent(event(android.view.MotionEvent.ACTION_MOVE, 125f, 169f))
        frame.dispatchTouchEvent(event(android.view.MotionEvent.ACTION_UP, 93f, 171f))
        assertEquals(1, last)
        last = 0
        frame.dispatchTouchEvent(event(android.view.MotionEvent.ACTION_DOWN, 55f, 160f))
        frame.dispatchTouchEvent(event(android.view.MotionEvent.ACTION_MOVE, 190f, 168f))
        frame.dispatchTouchEvent(event(android.view.MotionEvent.ACTION_UP, 210f, 169f))
        assertEquals(-1, last)
    }

}
