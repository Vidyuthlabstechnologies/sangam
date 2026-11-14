package com.sangam.app.network

import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query

// ---- REST: /campaigns -----------------------------------------------------
// Bulk AI calling toward a goal. See backend/app/api/campaigns.py.

data class CampaignCreateRequest(
    val name: String,
    val mode: String, // "live" or "simulation"
    val app_id: String?,
    val goal: String,
    val target_count: Int,
    val language: String,
    val pitch: String?,
    val business_name: String?,
    val concurrency: Int,
    val consent_confirmed: Boolean,
    val max_attempts: Int = 1,
    val success_variable: String = "goal_achieved",
    val success_values: List<String> = listOf("true", "yes"),
)

data class CampaignDemoRequest(
    val contacts: Int = 300,
    val target_count: Int = 50,
    val concurrency: Int = 100,
    val goal: String = "Site visit booked",
    val pitch: String = "Outer Ring Road villa plots",
    val business_name: String = "Sri Sai Developers",
    val start: Boolean = true,
)

data class ContactsUploadRequest(val csv: String)

data class CampaignDto(
    val id: String,
    val name: String,
    val mode: String,
    val app_id: String?,
    val goal: String,
    val target_count: Int,
    val language: String,
    val pitch: String?,
    val business_name: String?,
    val concurrency: Int,
    val window_start_hour: Int,
    val window_end_hour: Int,
    val status: String,
    val hold_reason: String?,
    val success_count: Int,
    val contacts_total: Int,
    val counts: Map<String, Int>?,
    val started_at: String?,
    val finished_at: String?,
    val created_at: String,
) {
    fun count(status: String): Int = counts?.get(status) ?: 0
    val isSimulation: Boolean get() = mode == "simulation"
    val isRunning: Boolean get() = status == "running"
}

data class InvalidRowDto(val line: Int, val reason: String)

data class ContactsUploadResult(
    val added: Int,
    val duplicates: Int,
    val suppressed: Int,
    val invalid_count: Int,
    val invalid: List<InvalidRowDto>?,
    val campaign: CampaignDto,
)

data class CampaignContactDto(
    val id: String,
    val name: String,
    val phone: String,
    val language: String?,
    val status: String,
    val attempts: Int,
    val succeeded: Boolean,
    val opted_out: Boolean,
    val summary: String?,
    val duration_seconds: Double?,
    val completed_at: String?,
)

data class CampaignTurnDto(val role: String, val content: String, val language: String? = null)

data class CampaignContactDetailDto(
    val id: String,
    val name: String,
    val phone: String,
    val language: String?,
    val status: String,
    val succeeded: Boolean,
    val summary: String?,
    val duration_seconds: Double?,
    val transcript: List<CampaignTurnDto>?,
)

data class ActiveCallDto(
    val id: String,
    val name: String,
    val phone: String,
    val language: String?,
    val phase: String, // "ringing" or "in_call"
    val elapsed_seconds: Int,
    val line: CampaignTurnDto?,
)

data class VersusTelecallerDto(
    val calls_finished: Int,
    val ai_elapsed_seconds: Int,
    val one_telecaller_seconds: Int,
    val telecallers_to_match: Int,
    val assumptions: String?,
)

data class CampaignLiveDto(
    val campaign: CampaignDto,
    val progress: Double,
    val active: List<ActiveCallDto>,
    val recent: List<CampaignContactDto>,
    val versus_telecaller: VersusTelecallerDto?,
    val simulated: Boolean,
)

interface SangamCampaignApi {
    @GET("/campaigns")
    suspend fun list(@Query("limit") limit: Int = 50): List<CampaignDto>

    @POST("/campaigns")
    suspend fun create(@Body body: CampaignCreateRequest): CampaignDto

    @POST("/campaigns/demo")
    suspend fun demo(@Body body: CampaignDemoRequest): CampaignDto

    @POST("/campaigns/{id}/contacts")
    suspend fun uploadContacts(@Path("id") id: String, @Body body: ContactsUploadRequest): ContactsUploadResult

    @POST("/campaigns/{id}/start")
    suspend fun start(@Path("id") id: String): CampaignDto

    @POST("/campaigns/{id}/pause")
    suspend fun pause(@Path("id") id: String): CampaignDto

    @POST("/campaigns/{id}/resume")
    suspend fun resume(@Path("id") id: String): CampaignDto

    @POST("/campaigns/{id}/cancel")
    suspend fun cancel(@Path("id") id: String): CampaignDto

    @GET("/campaigns/{id}/live")
    suspend fun live(@Path("id") id: String): CampaignLiveDto

    @GET("/campaigns/{id}/contacts")
    suspend fun contacts(
        @Path("id") id: String,
        @Query("succeeded") succeeded: Boolean? = null,
        @Query("limit") limit: Int = 200,
    ): List<CampaignContactDto>

    @GET("/campaigns/{id}/contacts/{cid}")
    suspend fun contact(@Path("id") id: String, @Path("cid") contactId: String): CampaignContactDetailDto
}
