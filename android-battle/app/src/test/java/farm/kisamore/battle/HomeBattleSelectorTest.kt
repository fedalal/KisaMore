package farm.kisamore.battle

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class HomeBattleSelectorTest {
    private fun battle(
        status: String = "open",
        id: String = "1",
        free: Int = 3,
        start: String? = null,
        cameras: List<CameraView> = emptyList(),
        entries: List<BattleEntry> = emptyList()
    ) = Battle(
        id = id, title = "Battle", status = status, rackId = 1,
        plantName = "Radish", growDays = 7,
        rackPhotoUrl = null, cameraViews = cameras,
        waterBudgetMl = 500, nutrientBudgetMl = 100, shadeBudgetMinutes = 60,
        winnerRewardKisa = 20, plantedAt = null, createdAt = null,
        entriesCount = 6 - free, maxEntries = 6, remainingEntries = free,
        entries = entries, predictionTotal = 0, predictionCounts = emptyMap(),
        myPredictionEntryId = null, startDate = start
    )

    private fun entry(full: String? = null, recent: String? = null) = BattleEntry(
        id = "entry", slotNumber = 1, status = "finished", isMine = false,
        resourcesVisible = true, waterUsedMl = 0, nutrientUsedMl = 0,
        shadeUsedMinutes = 0, actions = emptyList(),
        timelapse24hUrl = recent, timelapse3dUrl = null, certificateUrl = null,
        timelapseFullUrl = full
    )

    @Test fun nextBattleSkipsFullAndGrowing() {
        val full = battle(id = "full", free = 0)
        val growing = battle(id = "growing", status = "growing")
        val upcoming = battle(id = "upcoming", start = "2026-10-12")
        assertEquals("upcoming", HomeBattleSelector.nextOpenBattle(listOf(full, growing, upcoming))?.id)
        assertNull(HomeBattleSelector.nextOpenBattle(listOf(full, growing)))
    }

    @Test fun selectsEarliestOpenStartDate() {
        val later = battle(id = "later", start = "2026-10-30")
        val earlier = battle(id = "earlier", start = "2026-10-12")
        assertEquals("earlier", HomeBattleSelector.nextOpenBattle(listOf(later, earlier))?.id)
    }

    @Test fun mostFilledBattleShowsFirstWhenNoDateIsSet() {
        val nearlyFull = battle(id = "nearly", free = 1)
        val empty = battle(id = "empty", free = 6)
        assertEquals("nearly", HomeBattleSelector.nextOpenBattle(listOf(empty, nearlyFull))?.id)
    }

    @Test fun noBattleTimelapsesCanFallBackToRegularPlants() {
        val clip = HomeClip(null, "/rack/1/slot/1/timelapse/3d", false)
        assertEquals(clip, HomeBattleSelector.videoOptions(emptyList(), listOf(clip)).first())
    }

    @Test fun completeWholeShelfVideoPrecedesSinglePlant() {
        val finished = battle(
            status = "finished", id = "old", free = 0,
            cameras = listOf(BattleCamera("top", true, null, null, timelapseFullUrl = "/whole.mp4")),
            entries = listOf(entry(full = "/plant.mp4"))
        )
        val clips = HomeBattleSelector.videoOptions(listOf(finished))
        assertEquals("/whole.mp4", clips[0].path)
        assertTrue(clips[0].isWholeBattle)
        assertEquals("/plant.mp4", clips[1].path)
    }

    @Test fun fallingBackToIndividualPlantTimelapse() {
        val active = battle(status = "growing", entries = listOf(entry(recent = "/recent.mp4")))
        val clips = HomeBattleSelector.videoOptions(listOf(active))
        assertEquals("/recent.mp4", clips.first().path)
        assertTrue(!clips.first().isWholeBattle)
    }
}
