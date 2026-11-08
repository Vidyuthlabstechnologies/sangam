package com.sangam.app.network

import com.sangam.app.BuildConfig
import okhttp3.HttpUrl.Companion.toHttpUrlOrNull
import okhttp3.Interceptor
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.RequestBody
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.*
import java.util.concurrent.TimeUnit

data class WorkflowResponse(
    val id: String,
    val name: String,
    val description: String?,
    val initiator_id: String,
    val current_phase: String,
    val state: String,
    val phases: List<String>,
    val created_at: String,
    val updated_at: String,
    val approvals: List<ApprovalResponse> = emptyList(),
    val handoffs: List<HandoffResponse> = emptyList(),
    val exceptions: List<ExceptionResponse> = emptyList(),
)

data class WorkflowCreateRequest(
    val name: String,
    val description: String?,
    val initiator_id: String,
    val phases: List<String>? = null,
)

data class WorkflowListResponse(
    val items: List<WorkflowResponse>,
    val total: Int,
    val page: Int,
    val page_size: Int,
)

data class ApprovalResponse(
    val id: String,
    val workflow_id: String,
    val status: String,
    val required_actors: List<String>,
)

data class HandoffResponse(
    val id: String,
    val from_actor_id: String,
    val to_actor_id: String,
    val verified: Boolean,
)

data class ExceptionResponse(
    val id: String,
    val trigger: String,
    val severity: String,
    val message: String,
)

data class ActorResponse(
    val id: String,
    val type: String,
    val name: String,
    val email: String?,
    val roles: List<String>,
    val is_active: Boolean,
)

data class ActorCreateRequest(
    val type: String,
    val name: String,
    val email: String? = null,
    val roles: List<String> = emptyList(),
    val permissions: List<String> = emptyList(),
)


// ---- Vendors ----------------------------------------------------------

data class VendorLicenceDto(
    val id: String,
    val licence_type: String,
    val licence_number: String,
    val issuing_authority: String?,
    val issue_date: String?,
    val expiry_date: String?,
    val verified: Boolean,
    val extraction_confidence: Double?,
    val is_expired: Boolean = false,
    val days_until_expiry: Int?,
)

data class VendorDto(
    val id: String,
    val name: String,
    val legal_name: String?,
    val gstin: String?,
    val address: String?,
    val status: String,
    val created_at: String,
    val qualification_workflow_id: String?,
    val licences: List<VendorLicenceDto> = emptyList(),
    val has_expired_licence: Boolean = false,
    val is_qualifiable: Boolean = false,
)

data class CreateVendorRequest(
    val name: String,
    val gstin: String? = null,
    val address: String? = null,
    val contact_email: String? = null,
)

data class ExtractedDocumentDto(
    val id: String,
    val vendor_id: String?,
    val filename: String,
    val document_type: String,
    val status: String,
    val structured_data: Map<String, Any>? = null,
    val min_confidence: Double?,
    val needs_review: Boolean,
    val low_confidence_fields: Map<String, Double> = emptyMap(),
    val error_message: String?,
)

data class QualificationDto(
    val vendor_id: String,
    val workflow_id: String,
    val status: String,
    val message: String,
)

interface SangamApi {
    @GET("/workflows")
    suspend fun listWorkflows(
        @Query("page") page: Int = 1,
        @Query("page_size") pageSize: Int = 20,
    ): WorkflowListResponse

    @POST("/workflows")
    suspend fun createWorkflow(@Body request: WorkflowCreateRequest): WorkflowResponse

    @GET("/workflows/{id}")
    suspend fun getWorkflow(@Path("id") id: String): WorkflowResponse

    @PATCH("/workflows/{id}")
    suspend fun updateWorkflow(@Path("id") id: String, @Body body: Map<String, Any>): WorkflowResponse

    @POST("/workflows/{id}/pause")
    suspend fun pauseWorkflow(@Path("id") id: String): WorkflowResponse

    @POST("/workflows/{id}/resume")
    suspend fun resumeWorkflow(@Path("id") id: String): WorkflowResponse

    @POST("/workflows/{id}/cancel")
    suspend fun cancelWorkflow(@Path("id") id: String): WorkflowResponse

    @GET("/actors")
    suspend fun listActors(): List<ActorResponse>

    @POST("/actors")
    suspend fun createActor(@Body request: ActorCreateRequest): ActorResponse

    // ---- Vendors ----
    @GET("/vendors")
    suspend fun listVendors(): List<VendorDto>

    @GET("/vendors/{id}")
    suspend fun getVendor(@Path("id") id: String): VendorDto

    @POST("/vendors")
    suspend fun createVendor(@Body request: CreateVendorRequest): VendorDto

    @Multipart
    @POST("/vendors/{id}/documents")
    suspend fun uploadVendorDocument(
        @Path("id") id: String,
        @Part file: MultipartBody.Part,
        @Part("document_type") documentType: RequestBody,
    ): ExtractedDocumentDto

    @POST("/vendors/{vendorId}/documents/{docId}/confirm")
    suspend fun confirmDocument(
        @Path("vendorId") vendorId: String,
        @Path("docId") docId: String,
    ): VendorDto

    @POST("/vendors/{id}/submit-for-qualification")
    suspend fun submitForQualification(@Path("id") id: String): QualificationDto

    @GET("/vendors/expiring")
    suspend fun expiringVendors(@Query("days") days: Int = 90): List<VendorDto>

    @POST("/notifications/fcm/register")
    suspend fun registerFcmToken(@Body request: FCMTokenRequest): Map<String, String>
}

data class FCMTokenRequest(val token: String)

data class LLMRequest(
    val messages: List<LLMMessage>,
    val model: String = "sarvam-30b",
    val temperature: Float = 0.7f,
)

data class LLMMessage(
    val role: String,
    val content: String,
)

data class LLMResponse(
    val content: String,
    val model: String,
)

data class TranslateRequest(
    val text: String,
    val source_language_code: String = "auto",
    val target_language_code: String = "en-IN",
    val model: String = "mayura:v1",
    val mode: String = "formal",
)

data class TranslateResponse(
    val translated_text: String,
    val source_language_code: String,
)

data class STTResponse(
    val transcript: String,
    val language_code: String,
    val language_probability: Float,
    val timestamps: List<Map<String, Any>>? = null,
)

data class TTSRequest(
    val text: String,
    val target_language_code: String = "hi-IN",
    val speaker: String = "priya",
    val pace: Float = 1.0f,
    val pitch: Float = 0.0f,
    val loudness: Float = 1.0f,
)

data class InitiatePaymentRequest(
    val workflow_id: String,
    val amount: Double,
    val currency: String = "INR",
    val description: String? = null,
    val method: String? = null,
)

data class InitiatePaymentResponse(
    val payment_id: String,
    val razorpay_order_id: String,
    val razorpay_key_id: String,
    val amount: Double,
    val currency: String,
    val status: String,
)

data class VerifyPaymentRequest(
    val razorpay_order_id: String,
    val razorpay_payment_id: String,
    val razorpay_signature: String,
)

data class VerifyPaymentResponse(
    val status: String,
    val payment_id: String,
)

data class PaymentDetailResponse(
    val id: String,
    val workflow_id: String?,
    val amount: Double,
    val currency: String,
    val status: String,
    val method: String?,
    val description: String?,
    val created_at: String,
)

data class EscrowCreateRequest(
    val workflow_id: String,
    val payment_id: String,
    val amount: Double,
    val release_condition: String? = null,
)

data class EscrowResponse(
    val id: String,
    val status: String,
    val amount: Double,
)

data class InvoiceRequest(
    val workflow_id: String,
    val payment_id: String,
    val amount: Double,
    val description: String? = null,
    val tax_amount: Double = 0.0,
)

data class InvoiceResponse(
    val id: String,
    val invoice_number: String,
    val total_amount: Double,
    val status: String,
)

data class TTSResponse(
    val audio_base64: String,
    val request_id: String,
)

data class LanguagesResponse(
    val stt: List<String>,
    val tts: List<String>,
    val translate: List<String>,
)

data class VoicesResponse(
    val voices: Map<String, Any>,
)

interface SangamPaymentApi {
    @POST("/payments/initiate")
    suspend fun initiatePayment(@Body request: InitiatePaymentRequest): InitiatePaymentResponse

    @POST("/payments/verify")
    suspend fun verifyPayment(@Body request: VerifyPaymentRequest): VerifyPaymentResponse

    @GET("/payments/{paymentId}")
    suspend fun getPayment(@Path("paymentId") paymentId: String): PaymentDetailResponse

    @POST("/payments/{paymentId}/refund")
    suspend fun refundPayment(@Path("paymentId") paymentId: String, @Query("amount") amount: Double? = null): PaymentDetailResponse

    @POST("/payments/escrow")
    suspend fun createEscrow(@Body request: EscrowCreateRequest): EscrowResponse

    @POST("/payments/escrow/{escrowId}/release")
    suspend fun releaseEscrow(@Path("escrowId") escrowId: String): EscrowResponse

    @POST("/payments/escrow/{escrowId}/dispute")
    suspend fun disputeEscrow(@Path("escrowId") escrowId: String): EscrowResponse

    @POST("/payments/invoices")
    suspend fun createInvoice(@Body request: InvoiceRequest): InvoiceResponse

    @GET("/payments/invoices/{invoiceId}")
    suspend fun getInvoice(@Path("invoiceId") invoiceId: String): InvoiceResponse
}

interface SangamAiApi {
    @POST("/ai/llm")
    suspend fun llmComplete(@Body request: LLMRequest): LLMResponse

    @Multipart
    @POST("/ai/speech-to-text")
    suspend fun speechToText(
        @Part file: MultipartBody.Part,
        @Part("language_code") languageCode: RequestBody,
        @Part("mode") mode: RequestBody,
        @Part("with_timestamps") withTimestamps: RequestBody,
    ): STTResponse

    @POST("/ai/translate")
    suspend fun translate(@Body request: TranslateRequest): TranslateResponse

    @POST("/ai/text-to-speech")
    suspend fun textToSpeech(@Body request: TTSRequest): TTSResponse

    @POST("/ai/transliterate")
    suspend fun transliterate(@Body request: Map<String, String>): Map<String, String>

    @POST("/ai/identify-language")
    suspend fun identifyLanguage(@Query("text") text: String): Map<String, Any>

    @GET("/ai/languages")
    suspend fun listLanguages(): LanguagesResponse

    @GET("/ai/voices")
    suspend fun listVoices(): VoicesResponse
}

// ---- Sangamitra Mass-Launch Onboarding & Billing DTOs -----------------

data class UrlIngestRequestDto(
    val url: String,
    val languages: List<String> = listOf("kn-IN", "ml-IN", "te-IN"),
    val mascot_id: String = "v1",
    val category_id: String? = null,
)

data class VoiceNarrationRequestDto(
    val transcript: String,
    val language_code: String = "kn-IN",
    val mascot_id: String = "v1",
)

data class StarterPackActivateRequestDto(
    val user_id: String,
    val amount_inr: Double = 499.0,
    val upi_txn_id: String? = null,
    val deployment_id: String? = null,
)

data class WalletTopupRequestDto(
    val user_id: String,
    val amount_inr: Double,
    val upi_txn_id: String? = null,
)

data class ComposioConnectRequestDto(
    val user_id: String,
    val toolkit: String,
    val target_config: Map<String, Any> = emptyMap(),
)

data class SimForwardingRequestDto(
    val virtual_did: String,
    val carrier: String = "jio",
)

data class AiReportRequestDto(
    val user_id: String,
    val call_id: String,
    val reason: String,
    val transcript_snippet: String? = null,
)

data class PlanDto(
    val plan_id: String,
    val name: String,
    val audience: String,
    val validity_days: Int,
    val one_time: Boolean = false,
    val price_inr: Double,
    val gst_inr: Double,
    val total_payable_inr: Double,
    val included_minutes: Int,
    val wallet_credit_inr: Double,
    val overage_rate_per_min_inr: Double = 7.50,
)

data class PlansResponseDto(
    val gst_pct: Int = 18,
    val plans: List<PlanDto> = emptyList(),
)

data class CreateWalletOrderRequestDto(
    val plan_id: String? = null,
    val topup_amount_inr: Double? = null,
    val tenant_id: String? = null,
    val business_name: String? = null,
    val mascot_id: String? = null,
    val primary_language: String? = null,
    val gstin: String? = null,
)

data class CreateWalletOrderResponseDto(
    val order_id: String,
    val key_id: String? = null,
    val currency: String = "INR",
    val tenant_id: String,
    val purpose: String,
    val price_inr: Double,
    val gst_inr: Double,
    val amount_payable_inr: Double,
    val amount_paise: Long,
    val included_minutes: Int,
    val wallet_credit_inr: Double,
)

data class VerifyWalletPaymentRequestDto(
    val razorpay_order_id: String,
    val razorpay_payment_id: String,
    val razorpay_signature: String,
)

interface SangamOnboardingApi {
    @GET("/onboarding/categories")
    suspend fun getCategories(): Map<String, Any>

    @GET("/onboarding/plans")
    suspend fun getPlans(): PlansResponseDto

    @GET("/onboarding/vertical-packs")
    suspend fun getVerticalPacks(): Map<String, Any>

    @POST("/onboarding/ingest-url")
    suspend fun ingestUrl(@Body request: UrlIngestRequestDto): Map<String, Any>

    @POST("/onboarding/ingest-voice")
    suspend fun ingestVoice(@Body request: VoiceNarrationRequestDto): Map<String, Any>

    @POST("/onboarding/ingest-image")
    suspend fun ingestImageOcr(@Body request: Map<String, Any>): Map<String, Any>

    @POST("/onboarding/sim-forwarding-codes")
    suspend fun getSimForwardingCodes(@Body request: SimForwardingRequestDto): Map<String, Any>

    @GET("/onboarding/wallet/me")
    suspend fun getMyWallet(): Map<String, Any>

    @GET("/onboarding/wallet/{userId}")
    suspend fun getWallet(@Path("userId") userId: String): Map<String, Any>

    @POST("/onboarding/wallet/create-order")
    suspend fun createWalletOrder(@Body request: CreateWalletOrderRequestDto): CreateWalletOrderResponseDto

    @POST("/onboarding/wallet/verify-payment")
    suspend fun verifyWalletPayment(@Body request: VerifyWalletPaymentRequestDto): Map<String, Any>

    @POST("/onboarding/wallet/activate-starter-499")
    suspend fun activateStarter499(@Body request: StarterPackActivateRequestDto): Map<String, Any>

    @POST("/onboarding/wallet/topup")
    suspend fun topupWallet(@Body request: WalletTopupRequestDto): Map<String, Any>

    @POST("/onboarding/wallet/autopay")
    suspend fun configureAutopay(@Body request: Map<String, Any>): Map<String, Any>

    @POST("/onboarding/wallet/referral")
    suspend fun claimReferralBonus(@Body request: Map<String, String>): Map<String, Any>

    @GET("/onboarding/gst-invoice/{tenantId}")
    suspend fun getGstInvoice(@Path("tenantId") tenantId: String): Map<String, Any>

    @GET("/onboarding/viral-kit/{tenantId}")
    suspend fun getViralKit(@Path("tenantId") tenantId: String): Map<String, Any>

    @GET("/onboarding/composio/tools")
    suspend fun getComposioTools(@Query("user_id") userId: String? = null): Map<String, Any>

    @POST("/onboarding/composio/connect")
    suspend fun connectComposioTool(@Body request: ComposioConnectRequestDto): Map<String, Any>

    @POST("/onboarding/compliance/report-ai-output")
    suspend fun reportAiOutput(@Body request: AiReportRequestDto): Map<String, Any>

    @DELETE("/onboarding/compliance/account/{userId}")
    suspend fun deleteAccount(@Path("userId") userId: String): Map<String, Any>

    @GET("/agent-callbacks")
    suspend fun listCallbacks(
        @Query("status") status: String? = null,
        @Query("tenant_id") tenantId: String? = null,
    ): List<Map<String, Any>>

    @PATCH("/agent-callbacks/{callbackId}")
    suspend fun updateCallbackStatus(
        @Path("callbackId") callbackId: String,
        @Body body: Map<String, String>,
    ): Map<String, Any>
}

object ApiClient {
    private fun apiBaseUrl(): String {
        val raw = BuildConfig.API_BASE_URL.trim().trimEnd('/')
        return if (raw.isBlank()) "http://10.0.2.2:8000/" else "$raw/"
    }

    private val dynamicUrlInterceptor = Interceptor { chain ->
        var request = chain.request()
        val customUrl = TokenManager.getServerUrl()
        val parsed = customUrl.toHttpUrlOrNull()
        if (parsed != null) {
            val newUrl = request.url.newBuilder()
                .scheme(parsed.scheme)
                .host(parsed.host)
                .port(parsed.port)
                .build()
            request = request.newBuilder().url(newUrl).build()
        }
        chain.proceed(request)
    }

    private val loggingInterceptor = HttpLoggingInterceptor().apply {
        level = HttpLoggingInterceptor.Level.BODY
    }

    private val httpClient = OkHttpClient.Builder()
        .addInterceptor(dynamicUrlInterceptor)
        .addInterceptor(AuthInterceptor())
        .addInterceptor(loggingInterceptor)
        .connectTimeout(30, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .build()

    val api: SangamApi by lazy {
        Retrofit.Builder()
            .baseUrl(apiBaseUrl())
            .client(httpClient)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
            .create(SangamApi::class.java)
    }

    val authApi: AuthApi by lazy {
        Retrofit.Builder()
            .baseUrl(apiBaseUrl())
            .client(httpClient)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
            .create(AuthApi::class.java)
    }

    val paymentApi: SangamPaymentApi by lazy {
        Retrofit.Builder()
            .baseUrl(apiBaseUrl())
            .client(httpClient)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
            .create(SangamPaymentApi::class.java)
    }

    val aiApi: SangamAiApi by lazy {
        Retrofit.Builder()
            .baseUrl(apiBaseUrl())
            .client(httpClient.newBuilder().readTimeout(120, TimeUnit.SECONDS).build())
            .build()
            .let {
                Retrofit.Builder()
                    .baseUrl(apiBaseUrl())
                    .client(httpClient.newBuilder().readTimeout(120, TimeUnit.SECONDS).build())
                    .addConverterFactory(GsonConverterFactory.create())
                    .build()
                    .create(SangamAiApi::class.java)
            }
    }

    val onboardingApi: SangamOnboardingApi by lazy {
        Retrofit.Builder()
            .baseUrl(apiBaseUrl())
            .client(httpClient.newBuilder().readTimeout(60, TimeUnit.SECONDS).build())
            .addConverterFactory(GsonConverterFactory.create())
            .build()
            .create(SangamOnboardingApi::class.java)
    }
}
