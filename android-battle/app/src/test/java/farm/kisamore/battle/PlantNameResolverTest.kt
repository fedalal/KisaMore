package farm.kisamore.battle

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.RuntimeEnvironment

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class PlantNameResolverTest {
    @Test fun russianAppPrefersRussianPlantNameInsteadOfEnglishApiDefault() {
        val names = JSONObject("""{"en":"Arugula","ru":"Рукола","zh":"芝麻菜"}""")
        assertEquals("Рукола", PlantNameResolver.resolve(names, "ru", "Arugula"))
        assertEquals("芝麻菜", PlantNameResolver.resolve(names, "zh", "Arugula"))
        assertEquals("Arugula", PlantNameResolver.resolve(names, "en", "Arugula"))
    }

    @Test fun gracefullyFallsBackWhenTranslationMissing() {
        val names = JSONObject("""{"en":"Radish","ru":"Редис"}""")
        assertEquals("Radish", PlantNameResolver.resolve(names, "de", "Default"))
        assertEquals("Default", PlantNameResolver.resolve(JSONObject(), "ru", "Default"))
        assertEquals("Default", PlantNameResolver.resolve(null, "ru", "Default"))
    }

    @Test fun upcomingBattleUsesSelectedLanguageEvenAfterInitialDownload() {
        // Live API response is English by default but includes localized
        // plant_names. The UI must not depend on the language at fetch time.
        val names = PlantNameResolver.translations(JSONObject(
            """{"en":"Arugula","ru":"Руккола","zh":"芝麻菜","de":"Rucola","fr":"Roquette"}"""
        ))
        val battle = Battle(
            id = "battle1", title = "Upcoming", status = "open", rackId = 1,
            plantName = "Arugula", plantNames = names, growDays = 8,
            rackPhotoUrl = null,
            waterBudgetMl = 1000, nutrientBudgetMl = 200, shadeBudgetMinutes = 500,
            winnerRewardKisa = 20, plantedAt = null, createdAt = null,
            entriesCount = 1, maxEntries = 6, remainingEntries = 5,
            entries = emptyList(), predictionTotal = 0, predictionCounts = emptyMap(),
            myPredictionEntryId = null
        )
        val ctx = RuntimeEnvironment.getApplication()
        val settings = ctx.getSharedPreferences("battle_settings", 0)
        settings.edit().putString("language", "ru").commit()
        assertEquals("Руккола", battle.localizedPlantName(AppLanguage(ctx).code))
        settings.edit().putString("language", "en").commit()
        assertEquals("Arugula", battle.localizedPlantName(AppLanguage(ctx).code))
        settings.edit().putString("language", "zh").commit()
        assertEquals("芝麻菜", battle.localizedPlantName(AppLanguage(ctx).code))
        settings.edit().putString("language", "de").commit()
        assertEquals("Rucola", battle.localizedPlantName(AppLanguage(ctx).code))
        settings.edit().putString("language", "fr").commit()
        assertEquals("Roquette", battle.localizedPlantName(AppLanguage(ctx).code))
    }

    @Test fun missingLocaleFallsBackToEnglishName() {
        val translations = PlantNameResolver.translations(JSONObject(
            """{"en":"Radish","ru":"Редис"}"""
        ))
        assertEquals("Radish", PlantNameResolver.resolve(translations, "it", "Plant"))
        assertEquals("Редис", PlantNameResolver.resolve(translations, "ru-RU", "Plant"))
        assertEquals("Radish", PlantNameResolver.resolve(emptyMap(), "ru", "Radish"))
    }

    @Test fun authLabelsRespectSelectedEnglishLanguage() {
        val ctx = RuntimeEnvironment.getApplication()
        ctx.getSharedPreferences("battle_settings", 0).edit()
            .putString("language", "en").commit()
        val language = AppLanguage(ctx)
        assertEquals("BATTLE SIGN IN", language.t("ВХОД В BATTLE"))
        assertEquals("Create account", language.t("Создать аккаунт"))
        assertEquals("Close", language.t("Закрыть окно"))
        assertEquals("Password", language.t("Пароль"))
        assertEquals("Enter email and password", language.t("Введите email и пароль"))
    }
}
