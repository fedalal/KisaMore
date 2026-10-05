package farm.kisamore.battle

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import org.json.JSONArray
import org.json.JSONObject
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL

class ApiException(message: String, val statusCode: Int = 0) : IOException(message)

class ApiClient(context: Context) {
    private val prefs = context.getSharedPreferences("kisamore_battle_api", Context.MODE_PRIVATE)

    companion object {
        private const val PRIMARY_BASE_URL = "https://kisamore.farm"
        private const val FALLBACK_BASE_URL = "https://ru.kisamore.farm"
    }

    @Volatile
    private var activeBaseUrl: String = PRIMARY_BASE_URL

    val baseUrl: String
        get() = activeBaseUrl

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

    fun publicBattles(): List<Battle> =
        parseBattleArray(JSONArray(request("GET", "/api/v1/public/battles")))

    fun myBattles(): List<Battle> =
        parseBattleArray(JSONArray(request("GET", "/api/v1/battles/me")))

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
        val candidates = linkedSetOf(url)
        when {
            url.startsWith(PRIMARY_BASE_URL) ->
                candidates.add(url.replaceFirst(PRIMARY_BASE_URL, FALLBACK_BASE_URL))
            url.startsWith(FALLBACK_BASE_URL) ->
                candidates.add(url.replaceFirst(FALLBACK_BASE_URL, PRIMARY_BASE_URL))
        }

        for (candidate in candidates) {
            val connection = URL(candidate).openConnection() as HttpURLConnection
            try {
                connection.connectTimeout = 8_000
                connection.readTimeout = 20_000
                connection.setRequestProperty("Accept", "image/*")
                if (connection.responseCode in 200..299) {
                    if (candidate.startsWith(FALLBACK_BASE_URL)) activeBaseUrl = FALLBACK_BASE_URL
                    if (candidate.startsWith(PRIMARY_BASE_URL)) activeBaseUrl = PRIMARY_BASE_URL
                    return connection.inputStream.use { BitmapFactory.decodeStream(it) }
                }
            } catch (_: IOException) {
                // Try the alternate public server.
            } finally {
                connection.disconnect()
            }
        }
        return null
    }

    private fun request(method: String, path: String, body: String? = null): String {
        val first = activeBaseUrl
        val second = if (first == PRIMARY_BASE_URL) FALLBACK_BASE_URL else PRIMARY_BASE_URL

        try {
            return requestAgainst(first, method, path, body)
        } catch (firstError: Throwable) {
            if (!shouldTryAlternate(firstError)) throw firstError
            return try {
                requestAgainst(second, method, path, body).also {
                    activeBaseUrl = second
                }
            } catch (secondError: Throwable) {
                // Keep the error from the server currently preferred by the app unless
                // the alternate returned a meaningful API response.
                if (secondError is ApiException && !shouldTryAlternate(secondError)) {
                    throw secondError
                }
                throw firstError
            }
        }
    }

    private fun shouldTryAlternate(error: Throwable): Boolean {
        return when (error) {
            is ApiException -> error.statusCode in 500..599
            is IOException -> true
            else -> false
        }
    }

    private fun requestAgainst(
        serverBaseUrl: String,
        method: String,
        path: String,
        body: String?
    ): String {
        val connection = URL(serverBaseUrl + path).openConnection() as HttpURLConnection
        try {
            connection.requestMethod = method
            connection.connectTimeout = 8_000
            connection.readTimeout = 25_000
            connection.instanceFollowRedirects = true
            connection.setRequestProperty("Accept", "application/json")
            connection.setRequestProperty("User-Agent", "KisaMoreBattleAndroid/0.3")
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

            activeBaseUrl = serverBaseUrl
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
                                requestedAt = action.nullableString("requested_at")
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
                        certificateUrl = item.nullableString("certificate_url")
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

        return Battle(
            id = obj.optString("id"),
            title = obj.optString("title", "Plant Battle"),
            status = obj.optString("status"),
            rackId = obj.optInt("rack_id"),
            plantName = obj.optString("plant_name", "Plant"),
            growDays = obj.optInt("grow_days"),
            rackPhotoUrl = obj.nullableString("rack_photo_url"),
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
            myPredictionEntryId = obj.nullableString("my_prediction_entry_id")
        )
    }
}

private fun JSONObject.nullableString(key: String): String? {
    if (!has(key) || isNull(key)) return null
    return optString(key).takeIf { it.isNotBlank() && it != "null" }
}
