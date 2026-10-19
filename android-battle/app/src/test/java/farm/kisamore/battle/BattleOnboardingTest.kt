package farm.kisamore.battle

import android.app.Activity
import org.junit.Assert.assertFalse
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
    fun onboardingIsShownOnceAndCompletionSurvivesActivityRecreation() {
        val first = Robolectric.buildActivity(Activity::class.java).setup().get()
        assertTrue(BattleOnboarding.shouldShow(first))
        BattleOnboarding.markFinished(first)
        assertFalse(BattleOnboarding.shouldShow(first))

        val second = Robolectric.buildActivity(Activity::class.java).setup().get()
        assertFalse(BattleOnboarding.shouldShow(second))
    }

    @Test
    fun walkthroughLabelsAreAvailableInRussianAndEnglish() {
        val activity = Robolectric.buildActivity(Activity::class.java).setup().get()
        AppLanguage.set(activity, "ru")
        assertTrue(AppLanguage(activity).t("Оценить приложение") == "Оценить приложение")
        AppLanguage.set(activity, "en")
        assertTrue(AppLanguage(activity).t("Оценить приложение") == "Rate app")
        assertTrue(AppLanguage(activity).t("Пропустить обучение") == "Skip")
    }
}
