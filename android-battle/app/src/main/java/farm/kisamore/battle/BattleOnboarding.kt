package farm.kisamore.battle

import android.app.Activity
import android.app.AlertDialog
import android.content.Context

/**
 * Four short, opt-in steps for spectators and participants. Never simulates a
 * real watering/feeding command. Completion is kept on device across upgrades.
 */
internal object BattleOnboarding {
    private const val PREF = "kisamore_battle_onboarding"
    private const val DONE = "walkthrough_v1_finished"
    private var showing = false

    fun shouldShow(context: Context): Boolean =
        !context.getSharedPreferences(PREF, Context.MODE_PRIVATE).getBoolean(DONE, false)

    fun markFinished(context: Context) {
        context.getSharedPreferences(PREF, Context.MODE_PRIVATE).edit()
            .putBoolean(DONE, true).apply()
    }

    fun isShowing(): Boolean = showing

    /** @return true when the dialog is already visible or was just opened. */
    fun showIfNeeded(activity: Activity, onFinished: () -> Unit = {}): Boolean {
        if (showing) return true
        if (!shouldShow(activity)) return false
        show(activity, onFinished)
        return true
    }

    /** Reopen from Help without resetting first-launch completion state. */
    fun show(activity: Activity, onFinished: () -> Unit = {}) {
        if (showing || activity.isFinishing || activity.isDestroyed) return
        showing = true
        val language = AppLanguage(activity)
        val steps = listOf(
            "Растения настоящие" to
                "В KisaMore Battle вы наблюдаете за настоящими растениями в теплице. Шесть участников соревнуются на равных.",
            "Камеры и таймлапсы" to
                "Откройте вкладку «Битва»: слева выбирайте камеру, справа — таймлапс. Нажмите на фото, чтобы увеличить его.",
            "Ресурсы игрока" to
                "У каждого игрока ограничены вода, питательный раствор и время укрытия от света. Команды отправляются настоящему оборудованию. Зрители могут наблюдать без управления.",
            "Результаты и награды" to
                "Следите за ходом соревнования. В конце получите цифровой диплом, а победитель — награду Kisa."
        )
        fun finish() {
            showing = false
            markFinished(activity)
            onFinished()
        }
        fun openStep(index: Int) {
            if (activity.isFinishing || activity.isDestroyed) {
                showing = false
                return
            }
            AlertDialog.Builder(activity)
                .setTitle("${index + 1}/${steps.size} · ${language.t(steps[index].first)}")
                .setMessage(language.t(steps[index].second))
                .setNegativeButton(language.t("Пропустить обучение")) { _, _ -> finish() }
                .setPositiveButton(
                    language.t(if (index == steps.lastIndex) "Готово" else "Далее")
                ) { _, _ ->
                    if (index == steps.lastIndex) finish() else openStep(index + 1)
                }
                .setOnCancelListener { finish() }
                .show()
        }
        openStep(0)
    }
}
