package farm.kisamore.battle

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class BattleDayLabelTest {
    private fun battle(day: Int?, total: Int?, planted: String? = "2026-10-12T10:53:02Z") = Battle(
        id = "battle", title = "Battle 12-18", status = "growing", rackId = 1,
        plantName = "Radish", growDays = 10,
        rackPhotoUrl = null, waterBudgetMl = 500, nutrientBudgetMl = 100,
        shadeBudgetMinutes = 60, winnerRewardKisa = 20,
        plantedAt = planted, createdAt = null,
        entriesCount = 6, maxEntries = 6, remainingEntries = 0,
        entries = emptyList(), predictionTotal = 0, predictionCounts = emptyMap(),
        myPredictionEntryId = null, startDate = "2026-10-12", endDate = "2026-10-18",
        battleDay = day, battleTotalDays = total
    )

    @Test fun plantGrowingDaysNeverOverrideCompetitionDuration() {
        assertEquals("день 7 из 7", BattleDayLabel.text(battle(7, 7), "ru"))
        assertEquals("Day 7 of 7", BattleDayLabel.text(battle(7, 7), "en"))
        assertEquals("Tag 7 von 7", BattleDayLabel.text(battle(7, 7), "de"))
    }

    @Test fun scheduledBattleDoesNotStartWhenPhysicallyPlantedEarly() {
        assertNull(BattleDayLabel.text(battle(null, 7), "ru"))
        assertNull(BattleDayLabel.text(battle(1, 7, null), "ru"))
        assertNull(BattleDayLabel.text(battle(8, 7), "ru"))
    }
}
