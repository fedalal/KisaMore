package farm.kisamore.battle

import android.app.Activity
import android.view.View
import android.view.ViewGroup
import android.widget.TextView
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class BattleArenaLocalizationTest {
    private fun labels(view: View): List<String> {
        val out = mutableListOf<String>()
        fun walk(node: View) {
            if (node is TextView) out.add(node.text.toString())
            if (node is ViewGroup) for (i in 0 until node.childCount) walk(node.getChildAt(i))
        }
        walk(view)
        return out
    }

    private fun battle(entries: List<BattleEntry> = emptyList()) = Battle(
        id = "localized-battle",
        title = "Battle for herbs",
        status = "growing",
        rackId = 2,
        plantName = "Arugula",
        growDays = 8,
        rackPhotoUrl = null,
        waterBudgetMl = 1000,
        nutrientBudgetMl = 200,
        shadeBudgetMinutes = 180,
        winnerRewardKisa = 20,
        plantedAt = null,
        createdAt = null,
        entriesCount = entries.size,
        maxEntries = 6,
        remainingEntries = 6 - entries.size,
        entries = entries,
        predictionTotal = 0,
        predictionCounts = emptyMap(),
        myPredictionEntryId = null
    )

    private fun screen(host: Activity, battle: Battle) = BattleArenaScreen(
        host = host,
        api = ApiClient(host),
        battle = battle,
        choices = listOf(battle),
        cameraPreference = null,
        initialPeriod = 3,
        onBattle = {},
        onCamera = {},
        onPeriod = {},
        onCommand = { _, _ -> },
        onPhoto = {},
        onJournal = {},
        onPredict = {},
        onJoin = {}
    )

    private fun activity(locale: String): Activity {
        val host = Robolectric.buildActivity(Activity::class.java).setup().get()
        host.getSharedPreferences("battle_settings", 0).edit()
            .putString("language", locale).commit()
        return host
    }

    @Test fun englishSpectatorArenaContainsEnglishHeadingsAndInstructions() {
        val host = activity("en")
        val entry = BattleEntry(
            id = "e1", slotNumber = 1, status = "active",
            isMine = false, resourcesVisible = false,
            waterUsedMl = 0, nutrientUsedMl = 0, shadeUsedMinutes = 0,
            actions = emptyList(), timelapse24hUrl = null,
            timelapse3dUrl = null, certificateUrl = null, photoUrl = null,
            participantName = "Alice"
        )
        val all = labels(screen(host, battle(listOf(entry))))
        assertTrue(all.toString(), all.any { it.contains("LIVE · RACK 2") })
        assertTrue(all.toString(), all.contains("You are watching the battle"))
        assertTrue(all.toString(), all.contains("PARTICIPANTS"))
        assertTrue(all.toString(), all.any { it.contains("Tap a player") })
        assertFalse(all.toString(), all.any { it.contains("Вы наблюдаете") || it == "УЧАСТНИКИ" })
    }

    @Test fun englishOwnerArenaUsesEnglishResourcesAndActions() {
        val host = activity("en")
        val entry = BattleEntry(
            id = "me1", slotNumber = 2, status = "active",
            isMine = true, resourcesVisible = true,
            waterUsedMl = 55, nutrientUsedMl = 10, shadeUsedMinutes = 30,
            actions = emptyList(), timelapse24hUrl = null,
            timelapse3dUrl = null, certificateUrl = null, photoUrl = null,
        )
        val labels = labels(screen(host, battle(listOf(entry))))
        assertTrue(labels.toString(), labels.contains("MY RESOURCES"))
        assertTrue(labels.toString(), labels.contains("RECENT ACTIONS"))
        assertTrue(labels.toString(), labels.contains("Water"))
        assertTrue(labels.toString(), labels.contains("Nutrients"))
        assertTrue(labels.toString(), labels.contains("Shade"))
        assertTrue(labels.toString(), labels.contains("ACTIVITY"))
        assertTrue(labels.toString(), labels.any { it.contains("MY") || it.contains("MINE") })
        assertFalse(labels.toString(), labels.any { it == "МОИ РЕСУРСЫ" || it == "ПОСЛЕДНИЕ ДЕЙСТВИЯ" })
    }

    @Test fun russianArenaStillShowsRussianLabels() {
        val host = activity("ru")
        val labels = labels(screen(host, battle()))
        assertTrue(labels.toString(), labels.contains("Вы наблюдаете за битвой"))
        assertTrue(labels.toString(), labels.contains("УЧАСТНИКИ"))
    }

    @Test fun profileShowsRealKisaBalanceAtTopInEnglish() {
        val host = activity("en")
        val profile = BattleProfileScreen(
            host,
            UserInfo("user1", "Alice", "alice@example.test"),
            GameProfile(0, 1, 0, emptyList(), emptyList()),
            emptyList(),
            null,
            walletBalance = 42,
            onChangePhoto = {},
            onLogin = {},
            onPlant = {},
            onHistory = {},
            onRegion = {},
            onLogout = {}
        )
        val top = labels(profile.getChildAt(0))
        assertTrue(top.toString(), top.contains("Ⓚ 42"))
        assertTrue(profile.childCount >= 7)
    }

    @Test fun unavailableWalletIsNotSilentlyShownAsZero() {
        val host = activity("en")
        val profile = BattleProfileScreen(
            host,
            UserInfo("user2", "Bob", "bob@example.test"),
            GameProfile(0, 1, 0, emptyList(), emptyList()),
            emptyList(),
            null,
            walletBalance = null,
            onChangePhoto = {},
            onLogin = {},
            onPlant = {},
            onHistory = {},
            onRegion = {},
            onLogout = {}
        )
        assertTrue(labels(profile.getChildAt(0)).contains("Ⓚ —"))
    }
}
