package farm.kisamore.battle

data class BattleAction(
    val id: String,
    val kind: String,
    val amount: Int,
    val status: String,
    val requestedAt: String?
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
    val certificateUrl: String?,
    val timelapseFullUrl: String? = null
)

data class CameraView(
    val cameraId: String,
    val primary: Boolean,
    val photoUrl: String?,
    val timelapseFullUrl: String? = null,
    val timelapse3dUrl: String? = null,
    val timelapse24hUrl: String? = null
)

data class Battle(
    val id: String,
    val title: String,
    val status: String,
    val rackId: Int,
    val plantName: String,
    val growDays: Int,
    val rackPhotoUrl: String?,
    val cameraViews: List<CameraView>,
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
    val plantId: String? = null,
    val startDate: String? = null,
    val finishedAt: String? = null,
    val farmSlug: String? = null
) {
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
