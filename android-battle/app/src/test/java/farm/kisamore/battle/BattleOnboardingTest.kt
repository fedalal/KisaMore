package farm.kisamore.battle

import android.app.Activity
import android.graphics.Bitmap
import android.graphics.Canvas
import android.view.View
import org.junit.Assert.assertFalse
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
            "Начать", "Далее", "Оценить приложение", "Пригласить друга",
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
        }
    }
}
