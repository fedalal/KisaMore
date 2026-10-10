package farm.kisamore.battle

data class BattleCamera(
    val cameraId: String,
    val isPrimary: Boolean,
    val photoUrl: String?,
    val capturedAt: String?,
    val timelapse24hUrl: String? = null,
    val timelapse3dUrl: String? = null,
    val timelapseFullUrl: String? = null
)

data class BattleAction(
    val id: String,
    val kind: String,
    val amount: Int,
    val status: String,
    val requestedAt: String?,
    val completedAt: String? = null
)

data class BattleEntry(
    val id: String,
    val slotNumber: Int,
    val status: String,
    val isMine: Boolean,
    val resourcesVisible: Boolean,
    val waterUsedMl: Int,
    val nutrientUsedMl: Int,
    val shadeUsedMinutes: Int,
    val actions: List<BattleAction>,
    val timelapse24hUrl: String?,
    val timelapse3dUrl: String?,
    val timelapseFullUrl: String? = null,
    val certificateUrl: String?,
    val photoUrl: String?,
    val isWinner: Boolean = false,
    val badge: String? = null,
    val participantName: String? = null,
    val participantAvatarUrl: String? = null
)

data class Battle(
    val id: String,
    val title: String,
    val status: String,
    val rackId: Int,
    val plantName: String,
    val growDays: Int,
    val rackPhotoUrl: String?,
    val cameraViews: List<BattleCamera> = emptyList(),
    val waterBudgetMl: Int,
    val nutrientBudgetMl: Int,
    val shadeBudgetMinutes: Int,
    val winnerRewardKisa: Int,
    val plantedAt: String?,
    val createdAt: String?,
    val entriesCount: Int,
    val maxEntries: Int,
    val remainingEntries: Int,
    val entries: List<BattleEntry>,
    val predictionTotal: Int,
    val predictionCounts: Map<String, Int>,
    val myPredictionEntryId: String?,
    val winnerEntryId: String? = null,
    val finishedAt: String? = null,
    val plantId: String? = null,
    val farmSlug: String? = null,
    val startDate: String? = null,
    // Keep translations from the API. The language may change after battles
    // were downloaded, so the displayed name is resolved when drawing.
    val plantNames: Map<String, String> = emptyMap()
) {
    fun localizedPlantName(languageCode: String): String =
        PlantNameResolver.resolve(plantNames, languageCode, plantName)

    val mine: BattleEntry?
        get() = entries.firstOrNull { it.isMine }
}

data class UserInfo(
    val id: String,
    val displayName: String,
    val email: String
)

data class DailyMission(
    val key: String,
    val icon: String,
    val title: String,
    val reward: Int,
    val completed: Boolean
)

data class GameProfile(
    val xp: Int,
    val level: Int,
    val streak: Int,
    val missions: List<DailyMission>,
    val badges: List<String>
)

data class ServerReward(
    val id: String,
    val title: String,
    val icon: String,
    val earnedAt: String,
    val url: String?
)

data class PlayerBattleProfile(
    val battleCount: Int,
    val winCount: Int,
    val ratingPoints: Int,
    val rewards: List<ServerReward>,
    val finishedBattleIds: List<String>
)
