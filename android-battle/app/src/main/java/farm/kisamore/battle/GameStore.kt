package farm.kisamore.battle

import android.content.Context
import java.time.LocalDate
import java.time.temporal.ChronoUnit

class GameStore(context: Context) {
    private val prefs = context.getSharedPreferences("kisamore_battle_game", Context.MODE_PRIVATE)
    private val language = AppLanguage(context)

    fun openToday(): GameProfile {
        val today = LocalDate.now()
        val last = prefs.getString("last_open_date", null)?.let {
            runCatching { LocalDate.parse(it) }.getOrNull()
        }

        if (last != today) {
            val streak = when {
                last == null -> 1
                ChronoUnit.DAYS.between(last, today) == 1L -> prefs.getInt("streak", 0) + 1
                else -> 1
            }
            prefs.edit()
                .putInt("streak", streak)
                .putString("last_open_date", today.toString())
                .apply()
        }

        completeMission("open")
        return profile()
    }

    fun completeMission(key: String): GameProfile {
        val today = LocalDate.now()
        val storageKey = dayKey("mission_$key", today)
        if (!prefs.getBoolean(storageKey, false)) {
            prefs.edit()
                .putBoolean(storageKey, true)
                .putInt("xp", prefs.getInt("xp", 0) + rewardFor(key))
                .putBoolean("ever_$key", true)
                .apply()
        }
        return profile()
    }

    fun profile(): GameProfile {
        val today = LocalDate.now()
        val xp = prefs.getInt("xp", 0)
        val streak = prefs.getInt("streak", 1).coerceAtLeast(1)
        val missions = listOf(
            mission("open", "🌅", t("Зайти в теплицу"), 10, today),
            mission("predict", "🎯", t("Сделать прогноз"), 10, today),
            mission("video", "🎬", t("Посмотреть таймлапс"), 5, today),
            mission("command", "💧", t("Отдать команду растению"), 15, today)
        )
        val badges = buildList {
            if (xp >= 10) add(t("🌱 Первый рост"))
            if (prefs.getBoolean("ever_predict", false)) add(t("🎯 Аналитик"))
            if (prefs.getBoolean("ever_command", false)) add(t("🧠 Стратег"))
            if (prefs.getBoolean("ever_video", false)) add(t("🎬 Наблюдатель"))
            if (streak >= 3) add(t("🔥 Серия %d дней").replace("%d", streak.toString()))
            if (xp >= 200) add(t("🏅 Опытный садовод"))
        }
        return GameProfile(
            xp = xp,
            level = xp / 100 + 1,
            streak = streak,
            missions = missions,
            badges = badges
        )
    }

    private fun mission(
        key: String,
        icon: String,
        title: String,
        reward: Int,
        today: LocalDate
    ) = DailyMission(
        key = key,
        icon = icon,
        title = title,
        reward = reward,
        completed = prefs.getBoolean(dayKey("mission_$key", today), false)
    )

    private fun t(source: String): String = language.t(source)

    private fun rewardFor(key: String): Int = when (key) {
        "open" -> 10
        "predict" -> 10
        "video" -> 5
        "command" -> 15
        else -> 0
    }

    private fun dayKey(prefix: String, date: LocalDate): String = prefix + "_" + date
}
