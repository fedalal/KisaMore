package farm.kisamore.battle

import android.content.Context
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class BattleFirebaseTest {
    @Test fun firebaseMissingConfigurationCannotCrashLogin() {
        val app = RuntimeEnvironment.getApplication()
        val prefs = app.getSharedPreferences("kisamore_battle_api", Context.MODE_PRIVATE)
        prefs.edit().putString("session_cookie", "session=test").commit()
        try {
            // CI has no Firebase JSON; the app MUST still launch and log in.
            BattleFirebase.refresh(app)
            assertTrue(ApiClient(app).hasSession())
        } finally {
            prefs.edit().remove("session_cookie").commit()
        }
    }
}
