package farm.kisamore.battle

import android.Manifest
import android.app.job.JobScheduler
import android.content.Context
import android.content.pm.PackageManager
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.Shadows.shadowOf
import org.robolectric.annotation.Config

/**
 * Regression for 0.6.23 login/startup crash:
 * Android 14+ requires ACCESS_NETWORK_STATE for a constrained JobScheduler job.
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class BattleInboxJobTest {
    @Test
    fun signedInAppMayScheduleInboxCheckWithoutCrashing() {
        val context = RuntimeEnvironment.getApplication()
        assertEquals(
            "Android 14+ throws SecurityException without this manifest permission",
            PackageManager.PERMISSION_GRANTED,
            context.packageManager.checkPermission(
                Manifest.permission.ACCESS_NETWORK_STATE, context.packageName
            )
        )
        val prefs = context.getSharedPreferences("kisamore_battle_api", Context.MODE_PRIVATE)
        prefs.edit().putString("session_cookie", "session=fake-regression-test").commit()
        val consent = context.getSharedPreferences(
            "kisamore_battle_notification_consent", Context.MODE_PRIVATE)
        consent.edit().clear().commit()
        try {
            val scheduler = context.getSystemService(Context.JOB_SCHEDULER_SERVICE) as JobScheduler
            BattleInboxJob.schedule(context)
            assertNull("Notifications must wait for the user's explicit choice",
                scheduler.getPendingJob(69023))
            shadowOf(context).grantPermissions(Manifest.permission.POST_NOTIFICATIONS)
            BattleNotificationConsent.record(context, true)
            BattleInboxJob.schedule(context)
            BattleInboxJob.schedule(context) // safe on onResume too
            assertNotNull("Background notifications should be scheduled after consent",
                scheduler.getPendingJob(69023))
            BattleNotificationConsent.record(context, false)
            BattleInboxJob.schedule(context)
            assertNull("A declined notification preference cancels the job",
                scheduler.getPendingJob(69023))
        } finally {
            prefs.edit().remove("session_cookie").commit()
            consent.edit().clear().commit()
            BattleInboxJob.schedule(context)
        }
    }
}
