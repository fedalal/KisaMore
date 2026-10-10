package farm.kisamore.battle

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.net.Uri
import java.io.ByteArrayOutputStream
import org.json.JSONArray
import org.json.JSONObject
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL

class ApiException(message: String, val statusCode: Int = 0) : IOException(message)

class ApiClient(context: Context) {
    private val prefs = context.getSharedPreferences("kisamore_battle_api", Context.MODE_PRIVATE)
    private val primaryHost = "https://kisamore.farm"
    private val backupHost = "https://ru.kisamore.farm"

    init {
        if (!prefs.getBoolean("primary_host_migrated", false)) {
            prefs.edit().putString("base_url", primaryHost)
                .putBoolean("primary_host_migrated", true).apply()
        }
    }

    var baseUrl: String
        get() = prefs.getString("base_url", primaryHost) ?: primaryHost
        private set(value) = prefs.edit().putString("base_url", value.trimEnd('/')).apply()

    private var sessionCookie: String?
        get() = prefs.getString("session_cookie", null)
        set(value) {
            val edit = prefs.edit()
            if (value.isNullOrBlank()) edit.remove("session_cookie") else edit.putString("session_cookie", value)
            edit.apply()
        }

    var currentUser: UserInfo?
        get() {
            val id = prefs.getString("user_id", null) ?: return null
            return UserInfo(
                id = id,
                displayName = prefs.getString("user_name", "Игрок") ?: "Игрок",
                email = prefs.getString("user_email", "") ?: ""
            )
        }
        private set(value) {
            val edit = prefs.edit()
            if (value == null) {
                edit.remove("user_id").remove("user_name").remove("user_email")
            } else {
                edit.putString("user_id", value.id)
                    .putString("user_name", value.displayName)
                    .putString("user_email", value.email)
            }
            edit.apply()
        }

    fun hasSession(): Boolean = !sessionCookie.isNullOrBlank()

    fun setRegion(russian: Boolean) {
        baseUrl = if (russian) "https://ru.kisamore.farm" else "https://kisamore.farm"
    }

    fun isRussianServer(): Boolean = baseUrl.contains("ru.kisamore.farm")

    fun absolute(path: String?): String? {
        if (path.isNullOrBlank()) return null
        return if (path.startsWith("http://") || path.startsWith("https://")) path else baseUrl + path
    }

    fun login(email: String, password: String): UserInfo {
        val payload = JSONObject().put("email", email.trim()).put("password", password)
        val json = JSONObject(request("POST", "/api/v1/auth/login", payload.toString()))
        val user = UserInfo(
            id = json.optString("id"),
            displayName = json.optString("display_name", "Игрок"),
            email = json.optString("email", email.trim())
        )
        currentUser = user
        return user
    }

    fun logout() {
        runCatching { request("POST", "/api/v1/auth/logout") }
        sessionCookie = null
        currentUser = null
    }


    private val supportedLanguages = listOf("en","ru","zh","de","fr","es","it","pt","pl")

    fun fetchPreferences(): JSONObject =
        JSONObject(request("GET", "/api/v1/account/preferences"))

    fun savePreferences(language: String? = null, dark: Boolean? = null): JSONObject {
        val payload = JSONObject()
        if (language != null) {
            require(language in supportedLanguages) { "Unsupported language" }
            payload.put("language", language)
        }
        if (dark != null) payload.put("theme", if (dark) "dark" else "light")
        return JSONObject(request("PATCH", "/api/v1/account/preferences", payload.toString()))
    }

    fun uploadAvatar(content: ByteArray, mimeType: String): JSONObject {
        require(content.isNotEmpty() && content.size <= 2_097_152) { "Фотография не должна превышать 2 МБ" }
        val connection = URL(baseUrl + "/api/v1/account/avatar").openConnection() as HttpURLConnection
        try {
            connection.requestMethod = "POST"
            connection.connectTimeout = 12_000
            connection.readTimeout = 25_000
            connection.doOutput = true
            connection.setRequestProperty("Content-Type", mimeType)
            sessionCookie?.let { connection.setRequestProperty("Cookie", it) }
            connection.outputStream.use { it.write(content) }
            val code = connection.responseCode
            val response = (if (code in 200..299) connection.inputStream else connection.errorStream)
                ?.bufferedReader()?.use { it.readText() }.orEmpty()
            if (code !in 200..299) throw ApiException("Ошибка загрузки фото (HTTP $code)", code)
            return JSONObject(response)
        } finally { connection.disconnect() }
    }

    fun publicBattles(): List<Battle> =
        parseBattleArray(JSONArray(request("GET", "/api/v1/public/battles")))
    fun publicGrowthClips(farmSlug: String = "demo-farm"): List<HomeClip> {
        val market = JSONObject(request("GET", "/api/v1/public/farms/$farmSlug/market"))
        val racks = market.optJSONArray("racks") ?: return emptyList()
        val clips = mutableListOf<HomeClip>()
        for (i in 0 until racks.length()) {
            val rack = racks.optJSONObject(i) ?: continue
            val rackId = rack.optInt("rack_id")
            val slots = rack.optJSONArray("slots") ?: continue
            val posterUrl = rack.nullableString("photo_url")
            for (j in 0 until slots.length()) {
                val slotNumber = slots.optJSONObject(j)?.optInt("slot_number") ?: 0
                if (rackId <= 0 || slotNumber <= 0) continue
                val prefix = "/api/v1/public/farms/$farmSlug/racks/$rackId/slots/$slotNumber/timelapse/"
                clips.add(HomeClip(null, prefix + "3d", false, posterUrl))
                clips.add(HomeClip(null, prefix + "24h", false, posterUrl))
            }
        }
        return clips
    }


    fun myBattles(): List<Battle> =
        parseBattleArray(JSONArray(request("GET", "/api/v1/battles/me")))

    fun myBattleProfile(): PlayerBattleProfile {
        val json = JSONObject(request("GET", "/api/v1/battles/profile"))
        val awardRows = json.optJSONArray("rewards") ?: JSONArray()
        val rewards = buildList {
            for (i in 0 until awardRows.length()) {
                val row = awardRows.getJSONObject(i)
                add(ServerReward(
                    id = row.optString("id"),
                    title = row.optString("title"),
                    icon = row.optString("icon"),
                    earnedAt = row.optString("earned_at"),
                    url = row.nullableString("url")
                ))
            }
        }
        val histories = json.optJSONArray("history") ?: JSONArray()
        val ids = buildList {
            for (i in 0 until histories.length()) {
                add(histories.getJSONObject(i).optString("battle_id"))
            }
        }
        return PlayerBattleProfile(
            battleCount = json.optInt("battle_count"),
            winCount = json.optInt("win_count"),
            ratingPoints = json.optInt("rating_points"),
            rewards = rewards,
            finishedBattleIds = ids
        )
    }

    fun authenticatedBattle(id: String): Battle =
        parseBattle(JSONObject(request("GET", "/api/v1/battles/$id")))

    fun sendAction(battleId: String, entryId: String, kind: String, amount: Int) {
        val payload = JSONObject().put("kind", kind).put("amount", amount)
        request("POST", "/api/v1/battles/$battleId/entries/$entryId/actions", payload.toString())
    }

    fun predict(battleId: String, entryId: String): Battle {
        val payload = JSONObject().put("entry_id", entryId)
        return parseBattle(
            JSONObject(request("POST", "/api/v1/battles/$battleId/prediction", payload.toString()))
        )
    }

    fun joinBattle(battleId: String, quantity: Int = 1) {
        val payload = JSONObject().put("quantity", quantity)
        request("POST", "/api/v1/battles/$battleId/join", payload.toString())
    }

    fun loadBitmap(url: String?): Bitmap? {
        if (url.isNullOrBlank()) return null
        val connection = URL(url).openConnection() as HttpURLConnection
        return try {
            connection.connectTimeout = 10_000
            connection.readTimeout = 20_000
            connection.setRequestProperty("Accept", "image/*")
            if (url.startsWith(baseUrl + "/")) sessionCookie?.let {
                connection.setRequestProperty("Cookie", it)
            }
            connection.inputStream.use { BitmapFactory.decodeStream(it) }
        } catch (_: Exception) {
            null
        } finally {
            connection.disconnect()
        }
    }

    private fun request(method: String, path: String, body: String? = null): String {
        val host = baseUrl
        return try {
            requestOnHost(host, method, path, body)
        } catch (error: IOException) {
            // HTTP failures (including bad credentials) must never cause failover.
            if (error is ApiException || host != primaryHost) throw error
            val response = requestOnHost(backupHost, method, path, body)
            baseUrl = backupHost
            response
        }
    }

    private fun requestOnHost(host: String, method: String, path: String, body: String?): String {
        val connection = URL(host + path).openConnection() as HttpURLConnection
        try {
            connection.requestMethod = method
            connection.connectTimeout = 12_000
            connection.readTimeout = 25_000
            connection.instanceFollowRedirects = true
            connection.setRequestProperty("Accept", "application/json")
            connection.setRequestProperty("User-Agent", "KisaMoreBattleAndroid/0.2")
            sessionCookie?.let { connection.setRequestProperty("Cookie", it) }

            if (body != null) {
                connection.doOutput = true
                connection.setRequestProperty("Content-Type", "application/json; charset=utf-8")
                connection.outputStream.use { it.write(body.toByteArray(Charsets.UTF_8)) }
            }

            val code = connection.responseCode
            connection.headerFields["Set-Cookie"]
                ?.firstOrNull()
                ?.substringBefore(";")
                ?.takeIf { it.contains("=") }
                ?.let { sessionCookie = it }

            val stream = if (code in 200..299) connection.inputStream else connection.errorStream
            val response = stream?.bufferedReader()?.use { it.readText() }.orEmpty()

            if (code !in 200..299) {
                val detail = runCatching { JSONObject(response).optString("detail") }
                    .getOrNull().orEmpty()
                if (code == 401) {
                    sessionCookie = null
                    currentUser = null
                }
                throw ApiException(detail.ifBlank { "HTTP $code" }, code)
            }
            return response
        } finally {
            connection.disconnect()
        }
    }

    private fun parseBattleArray(array: JSONArray): List<Battle> = buildList {
        for (i in 0 until array.length()) add(parseBattle(array.getJSONObject(i)))
    }

    private fun parseBattle(obj: JSONObject): Battle {
        val entriesJson = obj.optJSONArray("entries") ?: JSONArray()
        val entries = buildList {
            for (i in 0 until entriesJson.length()) {
                val item = entriesJson.getJSONObject(i)
                val actionsJson = item.optJSONArray("actions") ?: JSONArray()
                val actions = buildList {
                    for (a in 0 until actionsJson.length()) {
                        val action = actionsJson.getJSONObject(a)
                        add(
                            BattleAction(
                                id = action.optString("id"),
                                kind = action.optString("kind"),
                                amount = action.optInt("amount"),
                                status = action.optString("status"),
                                requestedAt = action.nullableString("requested_at"),
                                completedAt = action.nullableString("completed_at")
                            )
                        )
                    }
                }
                add(
                    BattleEntry(
                        id = item.optString("id"),
                        slotNumber = item.optInt("slot_number"),
                        status = item.optString("status"),
                        isMine = item.optBoolean("is_mine", false),
                        resourcesVisible = item.optBoolean("resources_visible", false),
                        waterUsedMl = item.optInt("water_used_ml", 0),
                        nutrientUsedMl = item.optInt("nutrient_used_ml", 0),
                        shadeUsedMinutes = item.optInt("shade_used_minutes", 0),
                        actions = actions,
                        timelapse24hUrl = item.nullableString("timelapse_24h_url"),
                        timelapse3dUrl = item.nullableString("timelapse_3d_url"),
                        timelapseFullUrl = item.nullableString("timelapse_full_url"),
                        certificateUrl = item.nullableString("certificate_url"),
                        photoUrl = if (obj.optString("farm_slug").isBlank()) null else
                            "/api/v1/public/farms/" + obj.optString("farm_slug") +
                            "/racks/" + obj.optInt("rack_id") +
                            "/slots/" + item.optInt("slot_number") + "/photo",
                        isWinner = item.optBoolean("is_winner", false),
                        badge = item.nullableString("badge")
                    )
                )
            }
        }

        val predictionCounts = mutableMapOf<String, Int>()
        val counts = obj.optJSONObject("prediction_counts") ?: JSONObject()
        val keys = counts.keys()
        while (keys.hasNext()) {
            val key = keys.next()
            predictionCounts[key] = counts.optInt(key)
        }

        val cameraViewsJson = obj.optJSONArray("camera_views") ?: JSONArray()
        val cameras = buildList {
            for (i in 0 until cameraViewsJson.length()) {
                val row = cameraViewsJson.getJSONObject(i)
                add(BattleCamera(
                    cameraId = row.optString("camera_id"),
                    isPrimary = row.optBoolean("primary"),
                    photoUrl = row.nullableString("photo_url"),
                    capturedAt = row.nullableString("captured_at"),
                    timelapse24hUrl = row.optJSONObject("timelapse_urls")?.nullableString("24h"),
                    timelapse3dUrl = row.optJSONObject("timelapse_urls")?.nullableString("3d"),
                    timelapseFullUrl = row.optJSONObject("timelapse_urls")?.nullableString("full")
                ))
            }
        }

        return Battle(
            id = obj.optString("id"),
            title = obj.optString("title", "Plant Battle"),
            status = obj.optString("status"),
            rackId = obj.optInt("rack_id"),
            plantName = obj.optString("plant_name", "Plant"),
            growDays = obj.optInt("grow_days"),
            rackPhotoUrl = obj.nullableString("rack_photo_url"),
            cameraViews = cameras,
            waterBudgetMl = obj.optInt("water_budget_ml"),
            nutrientBudgetMl = obj.optInt("nutrient_budget_ml"),
            shadeBudgetMinutes = obj.optInt("shade_budget_minutes"),
            winnerRewardKisa = obj.optInt("winner_reward_kisa"),
            plantedAt = obj.nullableString("planted_at"),
            createdAt = obj.nullableString("created_at"),
            entriesCount = obj.optInt("entries_count"),
            maxEntries = obj.optInt("max_entries", 6),
            remainingEntries = obj.optInt("remaining_entries"),
            entries = entries,
            predictionTotal = obj.optInt("prediction_total"),
            predictionCounts = predictionCounts,
            myPredictionEntryId = obj.nullableString("my_prediction_entry_id"),
            winnerEntryId = obj.nullableString("winner_entry_id"),
            finishedAt = obj.nullableString("finished_at"),
            plantId = obj.nullableString("plant_id"),
            farmSlug = obj.nullableString("farm_slug"),
            startDate = obj.nullableString("start_date")
        )
    }
}

private fun JSONObject.nullableString(key: String): String? {
    if (!has(key) || isNull(key)) return null
    return optString(key).takeIf { it.isNotBlank() && it != "null" }
}
