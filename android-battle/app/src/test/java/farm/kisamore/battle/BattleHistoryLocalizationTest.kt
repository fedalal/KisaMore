package farm.kisamore.battle

import android.app.Activity
import android.view.View
import android.view.ViewGroup
import android.widget.TextView
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class BattleHistoryLocalizationTest {
    private fun activity(locale: String): Activity =
        Robolectric.buildActivity(Activity::class.java).setup().get().also {
            AppLanguage.set(it, locale)
        }

    private fun visibleTexts(root: View): List<String> {
        val texts = mutableListOf<String>()
        fun visit(view: View) {
            if (view is TextView) texts += view.text.toString()
            if (view is ViewGroup) for (i in 0 until view.childCount) visit(view.getChildAt(i))
        }
        visit(root)
        return texts
    }

    private fun battle(isWinner: Boolean): Battle {
        val mine = BattleEntry(
            id = "entry-1", slotNumber = 1, status = "finished",
            isMine = true, resourcesVisible = true,
            waterUsedMl = 150, nutrientUsedMl = 0, shadeUsedMinutes = 0,
            actions = emptyList(), timelapse24hUrl = null, timelapse3dUrl = null,
            certificateUrl = null, photoUrl = null, isWinner = isWinner
        )
        return Battle(
            id = "completed", title = "Arugula challenge", status = "finished",
            rackId = 1, plantName = "Руккола", growDays = 8, rackPhotoUrl = null,
            waterBudgetMl = 600, nutrientBudgetMl = 100, shadeBudgetMinutes = 120,
            winnerRewardKisa = 20, plantedAt = "2026-09-24",
            createdAt = "2026-09-24", entriesCount = 1, maxEntries = 6,
            remainingEntries = 0, entries = listOf(mine),
            predictionTotal = 0, predictionCounts = emptyMap(),
            myPredictionEntryId = null, finishedAt = "2026-10-02T12:00:00",
            plantNames = mapOf("en" to "Arugula", "de" to "Rucola")
        )
    }

    private fun history(activity: Activity, battles: List<Battle> = emptyList()) =
        BattleHistoryScreen(
            host = activity, battles = battles, api = ApiClient(activity),
            onViewBattle = {}, onPhoto = {}, onVideo = {},
            onCertificate = {}, onCurrentBattle = {}
        )

    @Test fun emptyHistoryIsEnglishWhenEnglishSelected() {
        val host = activity("en")
        val values = visibleTexts(history(host))
        assertTrue(values.toString(), values.contains("History"))
        assertTrue(values.toString(), values.contains("Your completed battles"))
        assertTrue(values.toString(), values.contains("No completed battles yet"))
        assertTrue(values.toString(), values.contains("Watch current battle"))
        assertTrue(values.toString(), values.any { it.contains("digital certificate") })
        assertFalse(values.toString(), values.any { it.contains("История") || it.contains("Пока нет") })
    }

    @Test fun finishedHistoryIsEnglishIncludingResultAndActions() {
        val host = activity("en")
        val values = visibleTexts(history(host, listOf(battle(true))))
        for (label in listOf("History", "COMPLETED", "WINS", "CERTIFICATES",
                "Completed battles", "Arugula", "Victory", "Photo", "Timelapse", "Certificate")) {
            assertTrue("Missing English label " + label + ": " + values, label in values)
        }
        assertTrue(values.toString(), values.contains("Finished: 2026-10-02"))
        assertFalse(values.toString(), values.any { it.contains("Завершено:") || it == "Победа" })
    }

    @Test fun switchingLocaleUpdatesNewHistoryScreens() {
        val host = activity("ru")
        assertTrue(visibleTexts(history(host)).contains("История"))
        AppLanguage.set(host, "en")
        assertTrue(visibleTexts(history(host)).contains("History"))
        AppLanguage.set(host, "de")
        assertTrue(visibleTexts(history(host)).contains("Verlauf"))
        assertTrue(visibleTexts(history(host, listOf(battle(false)))).contains("Teilnahme"))
    }

    @Test fun startupConnectionMessageUsesSelectedLanguage() {
        val host = activity("en")
        assertEquals("Connecting to the greenhouse…",
            AppLanguage(host).t("Подключаемся к теплице…"))
        AppLanguage.set(host, "ru")
        assertEquals("Подключаемся к теплице…",
            AppLanguage(host).t("Подключаемся к теплице…"))
    }
}
