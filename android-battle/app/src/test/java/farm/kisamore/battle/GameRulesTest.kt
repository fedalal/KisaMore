package farm.kisamore.battle

import org.junit.Assert.assertEquals
import org.junit.Test

class GameRulesTest {
    @Test
    fun remainingNeverGoesBelowZero() {
        assertEquals(0, GameRules.remaining(100, 150))
    }

    @Test
    fun progressShowsRemainingShare() {
        assertEquals(0.75f, GameRules.progress(1000, 250), 0.0001f)
    }

    @Test
    fun zeroBudgetIsSafe() {
        assertEquals(0f, GameRules.progress(0, 0), 0.0001f)
    }
}
