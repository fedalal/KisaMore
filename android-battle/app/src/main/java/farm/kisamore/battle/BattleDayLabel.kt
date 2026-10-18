package farm.kisamore.battle

/**
 * The API calculates inclusive competition days from the scheduled
 * start_date/end_date in the farm timezone, never from Plant.grow_days.
 */
internal object BattleDayLabel {
    fun text(battle: Battle, languageCode: String = "ru"): String? {
        if (battle.plantedAt.isNullOrBlank()) return null
        val day = battle.battleDay ?: return null
        val total = battle.battleTotalDays ?: return null
        if (day !in 1..total) return null
        return when (languageCode) {
            "ru" -> "день $day из $total"
            "de" -> "Tag $day von $total"
            "fr" -> "jour $day sur $total"
            "es" -> "día $day de $total"
            "it" -> "giorno $day di $total"
            "pt" -> "dia $day de $total"
            "pl" -> "dzień $day z $total"
            "zh" -> "第 $day/$total 天"
            else -> "Day $day of $total"
        }
    }
}
