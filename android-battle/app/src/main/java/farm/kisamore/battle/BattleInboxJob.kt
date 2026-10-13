package farm.kisamore.battle

import android.Manifest
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.job.JobInfo
import android.app.job.JobParameters
import android.app.job.JobScheduler
import android.app.job.JobService
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.util.Log
import org.json.JSONObject

/** Periodic system notifications; messages are persistent on the server.
 * Doze may delay jobs. An actual immediate push transport needs FCM setup.
 */
class BattleInboxJob : JobService() {
    companion object {
        private const val JOB_ID = 69023
        private const val CHANNEL = "battle_admin_messages"

        fun schedule(context: Context) {
            // Background notifications are optional. Missing OS permissions,
            // OEM JobScheduler restrictions and invalid job configuration must
            // NEVER crash login, onResume or cold app launch.
            try {
                val api = ApiClient(context.applicationContext)
                val scheduler = context.getSystemService(Context.JOB_SCHEDULER_SERVICE)
                    as? JobScheduler ?: return
                if (!api.hasSession()) {
                    scheduler.cancel(JOB_ID)
                    return
                }
                // onCreate and onResume both call this. Do not re-register an
                // existing persisted job on every screen unlock.
                if (scheduler.getPendingJob(JOB_ID) != null) return

                val job = JobInfo.Builder(JOB_ID, ComponentName(context, BattleInboxJob::class.java))
                    .setRequiredNetworkType(JobInfo.NETWORK_TYPE_ANY)
                    .setPeriodic(15 * 60 * 1000L)
                    .setPersisted(true)
                    .build()
                if (scheduler.schedule(job) != JobScheduler.RESULT_SUCCESS) {
                    Log.w("BattleInboxJob", "Background notification job was not scheduled")
                }
            } catch (exc: RuntimeException) {
                Log.e("BattleInboxJob", "Could not schedule notifications; app will continue", exc)
            }
        }

        fun notifyNew(context: Context, json: JSONObject) {
            if (Build.VERSION.SDK_INT >= 33 &&
                context.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) !=
                    PackageManager.PERMISSION_GRANTED) return
            val mgr = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            mgr.createNotificationChannel(NotificationChannel(
                CHANNEL, "KisaMore Battle messages", NotificationManager.IMPORTANCE_DEFAULT
            ))
            val messages = json.optJSONArray("messages") ?: return
            val prefs = context.getSharedPreferences("battle_message_notifications", Context.MODE_PRIVATE)
            val api = ApiClient(context.applicationContext)
            val account = api.currentUser?.id ?: return
            val key = "seen_$account"
            val seen = prefs.getStringSet(key, emptySet()).orEmpty().toMutableSet()
            var changed = false
            for (i in 0 until messages.length()) {
                val m = messages.getJSONObject(i)
                val id = m.optString("id")
                if (id.isBlank() || !m.isNull("read_at") || id in seen) continue
                seen.add(id)
                changed = true
                val intent = Intent(context, MainActivity::class.java).apply {
                    addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP)
                    putExtra("open_battle_inbox", true)
                }
                val pending = PendingIntent.getActivity(context, i + 1, intent,
                    PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
                val notification = Notification.Builder(context, CHANNEL)
                    .setSmallIcon(R.drawable.ic_kisamore_launcher)
                    .setContentTitle("KisaMore · " + m.optString("battle_title"))
                    .setContentText(m.optString("body").take(160))
                    .setStyle(Notification.BigTextStyle().bigText(m.optString("body")))
                    .setAutoCancel(true)
                    .setContentIntent(pending)
                    .build()
                mgr.notify(id.hashCode(), notification)
            }
            if (changed) prefs.edit().putStringSet(key, seen.take(100).toSet()).apply()
        }
    }

    override fun onStartJob(params: JobParameters): Boolean {
        Thread {
            try {
                val api = ApiClient(applicationContext)
                if (api.hasSession()) notifyNew(applicationContext, api.battleInbox())
            } catch (_: Exception) {
                // A later poll will still find the message in the inbox.
            } finally {
                jobFinished(params, false)
            }
        }.start()
        return true
    }

    override fun onStopJob(params: JobParameters): Boolean = true
}
