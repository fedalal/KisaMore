package farm.kisamore.battle

object GameRules {
    fun remaining(budget: Int, used: Int): Int = (budget - used).coerceAtLeast(0)

    fun progress(budget: Int, used: Int): Float {
        if (budget <= 0) return 0f
        return (remaining(budget, used).toFloat() / budget.toFloat()).coerceIn(0f, 1f)
    }
}
