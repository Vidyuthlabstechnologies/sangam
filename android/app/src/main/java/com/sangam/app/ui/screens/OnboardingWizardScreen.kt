package com.sangam.app.ui.screens

import com.sangam.app.ui.components.str

import com.sangam.app.ui.components.SecondaryButton
import com.sangam.app.ui.components.PrimaryButton
import android.content.Context
import android.content.Intent
import android.graphics.BitmapFactory
import android.media.MediaPlayer
import android.net.Uri
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.toggleable
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.automirrored.filled.VolumeUp
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.sangam.app.ui.components.BackButton
import com.sangam.app.ui.components.friendlyError
import com.sangam.app.R
import com.sangam.app.network.*
import com.sangam.app.ui.theme.*
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import com.sangam.app.billing.Billing

data class MascotOption(
    val id: String,
    val name: String,
    val style: String,
    val tagline: String,
)

val AVAILABLE_MASCOTS = listOf(
    MascotOption("kite", "Kite Master", "Aviator Kite with Headset", "Friendly aviator with a headset"),
    MascotOption("v1", "Mitra", "Minimalist Editorial Ink", "Crisp ink-brush guide on pure white"),
    MascotOption("v2", "Swar", "Ceramic & Obsidian Voice Pod", "Tactile 3D studio hardware aesthetic"),
    MascotOption("v3", "Vani", "Artisan Flat Vector Concierge", "Warm Indian geometric vector receptionist"),
)

val THREE_MASCOTS = AVAILABLE_MASCOTS

val MASCOT_POSES = listOf("idle", "thinking", "victory", "peekaboo", "frozen", "adjudicator")

val VERTICAL_PACK_CHIPS = listOf(
    "b2b_minerals" to R.string.pack_b2b_minerals,
    "csc_meeseva" to R.string.pack_csc_meeseva,
    "dental_clinic" to R.string.pack_dental_clinic,
    "real_estate" to R.string.pack_real_estate,
    "restaurant_cloud" to R.string.pack_restaurant_cloud,
    "salon_bridal" to R.string.pack_salon_bridal,
    "auto_service" to R.string.pack_auto_service,
    "ca_tax_legal" to R.string.pack_ca_tax_legal,
    "hotel_resort" to R.string.pack_hotel_resort,
    "hardware_tiles" to R.string.pack_hardware_tiles,
    "jewellery_bullion" to R.string.pack_jewellery_bullion,
    "personal_vip" to R.string.pack_personal_vip,
)

@Composable
fun MascotAvatar(
    mascotId: String,
    pose: String = "idle",
    sizeDp: Int = 56,
) {
    if (mascotId == "kite") {
        val resId = when (pose.lowercase()) {
            "thinking", "scanning" -> R.drawable.mascot_kite_thinking
            "celebration", "victory", "guidance" -> R.drawable.mascot_kite_victory
            "peekaboo" -> R.drawable.mascot_kite_peekaboo
            "frozen" -> R.drawable.mascot_kite_frozen
            "adjudicator" -> R.drawable.mascot_kite_adjudicator
            else -> R.drawable.mascot_kite_idle
        }
        Box(
            modifier = Modifier.size(sizeDp.dp),
            contentAlignment = Alignment.Center,
        ) {
            Image(
                painter = painterResource(resId),
                contentDescription = null,
                contentScale = ContentScale.Fit,
                modifier = Modifier.fillMaxSize(),
            )
        }
        return
    }

    val context = LocalContext.current
    val bitmap = remember(mascotId, pose) {
        try {
            context.assets.open("mascots/${mascotId}_${pose}.jpg").use { stream ->
                BitmapFactory.decodeStream(stream)?.asImageBitmap()
            }
        } catch (_: Exception) {
            null
        }
    }
    Box(
        modifier = Modifier
            .size(sizeDp.dp)
            .clip(RoundedCornerShape(12.dp))
            .background(SangamAlabaster)
            .border(1.dp, SangamBorder, RoundedCornerShape(12.dp)),
        contentAlignment = Alignment.Center,
    ) {
        if (bitmap != null) {
            Image(
                bitmap = bitmap,
                contentDescription = null,
                contentScale = ContentScale.Crop,
                modifier = Modifier.fillMaxSize(),
            )
        } else {
            Icon(
                Icons.Default.RecordVoiceOver,
                contentDescription = null,
                tint = SangamObsidian,
            )
        }
    }
}


/** Languages a caller can be answered in. Labels are in the language itself so owners find theirs. */
val AGENT_LANGUAGES = listOf(
    "hi-IN" to "हिन्दी",
    "en-IN" to "English",
    "kn-IN" to "ಕನ್ನಡ",
    "ta-IN" to "தமிழ்",
    "te-IN" to "తెలుగు",
    "ml-IN" to "മലയാളം",
    "mr-IN" to "मराठी",
    "bn-IN" to "বাংলা",
    "gu-IN" to "ગુજરાતી",
    "pa-IN" to "ਪੰਜਾਬੀ",
    "od-IN" to "ଓଡ଼ିଆ",
)

/** Apps the agent can update after a call. Ids are the backend's toolkit names. */
private val APP_INTEGRATIONS = listOf(
    Triple("WHATSAPP", "WhatsApp", R.string.app_whatsapp),
    Triple("GOOGLESHEETS", "Google Sheets", R.string.app_googlesheets),
    Triple("GOOGLECALENDAR", "Google Calendar", R.string.app_googlecalendar),
    Triple("TALLY_PRIME", "Tally Prime", R.string.app_tally_prime),
    Triple("INDIAMART", "IndiaMART", R.string.app_indiamart),
    Triple("ZOHO_CRM", "Zoho CRM", R.string.app_zoho_crm),
    Triple("SHOPIFY", "Shopify", R.string.app_shopify),
    Triple("SHIPROCKET", "Shiprocket", R.string.app_shiprocket),
    Triple("GMAIL", "Gmail", R.string.app_gmail),
    Triple("TELEGRAM", "Telegram", R.string.app_telegram),
)

private fun dialable(phone: String): String? =
    phone.filter { it.isDigit() || it == '+' }.takeIf { it.count(Char::isDigit) >= 10 }

@OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class)
@Composable
fun OnboardingWizardScreen(
    onBack: () -> Unit = {},
    onOpenCallInbox: () -> Unit = {},
    onAccountDeleted: () -> Unit = {},
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val prefs = remember { context.getSharedPreferences("sangamitra_prefs", Context.MODE_PRIVATE) }

    var selectedMascot by remember { mutableStateOf(prefs.getString("selected_mascot", "kite") ?: "kite") }
    var currentPose by remember { mutableStateOf("idle") }
    var selectedPack by remember { mutableStateOf<String?>(null) }
    var selectedLanguage by remember { mutableStateOf(prefs.getString("agent_language", "hi-IN") ?: "hi-IN") }
    var targetUrl by remember { mutableStateOf("") }
    var urlError by remember { mutableStateOf<String?>(null) }
    var description by remember { mutableStateOf("") }
    var statusBanner by remember {
        mutableStateOf(str(R.string.paste_your_website_or_google_maps))
    }
    var isBusy by remember { mutableStateOf(false) }

    // Live provisioned agent state. Null means "not set up yet".
    var deployedPhone by remember { mutableStateOf<String?>(null) }
    var deployedBusiness by remember { mutableStateOf<String?>(null) }
    var defaultLanguage by remember { mutableStateOf<String?>(null) }

    var playingAudioAsset by remember { mutableStateOf<String?>(null) }
    var mediaPlayer by remember { mutableStateOf<MediaPlayer?>(null) }

    var plans by remember {
        mutableStateOf(
            listOf(
                PlanDto("pilot", str(R.string.n_7_day_live_pilot), str(R.string.try_it_on_a_real_number), 7, true, 799.0, 143.82, 942.82, 85, 651.50),
                PlanDto("personal", str(R.string.mitra_personal), str(R.string.individuals_creators), 30, false, 999.0, 179.82, 1178.82, 113, 851.50),
                PlanDto("vyapar", str(R.string.vyapar_starter), str(R.string.shops_clinics_smbs), 30, false, 2499.0, 449.82, 2948.82, 313, 2351.50),
                PlanDto("udyog", str(R.string.udyog_b2b_pro), str(R.string.manufacturing_b2b_desks), 30, false, 4999.0, 899.82, 5898.82, 646, 4851.50),
                PlanDto("enterprise", str(R.string.enterprise), str(R.string.multi_branch_high_volume), 30, false, 11999.0, 2159.82, 14158.82, 1579, 11851.50),
            )
        )
    }
    var selectedPlanId by remember { mutableStateOf("vyapar") }
    var walletBalanceInr by remember { mutableStateOf(0.0) }
    var isStarterActive by remember { mutableStateOf(false) }
    var referralCode by remember { mutableStateOf("") }

    LaunchedEffect(Unit) {
        try {
            val response = ApiClient.onboardingApi.getPlans()
            if (response.plans.isNotEmpty()) {
                plans = response.plans
            }
        } catch (_: Exception) { }

        try {
            val w = ApiClient.onboardingApi.getMyWallet()
            (w["call_balance_inr"] as? Number)?.toDouble()?.let { walletBalanceInr = it }
            isStarterActive = (w["deployment_status"] as? String) == "ACTIVE"
            (w["referral_code"] as? String)?.takeIf { it.isNotBlank() }?.let { referralCode = it }
            (w["assigned_did"] as? String)?.takeIf { it.isNotBlank() }?.let { deployedPhone = it }
            (w["business_name"] as? String)?.takeIf { it.isNotBlank() }?.let { deployedBusiness = it }
            (w["primary_language"] as? String)?.takeIf { it.isNotBlank() }?.let { defaultLanguage = it }
        } catch (e: Exception) {
            statusBanner = friendlyError(e, str(R.string.load_your_agent))
        }
    }

    var showDeleteConfirmDialog by remember { mutableStateOf(false) }
    var showReportAiDialog by remember { mutableStateOf(false) }
    var showForwardOffDialog by remember { mutableStateOf(false) }

    // Nothing is connected until the owner turns it on here.
    val connectedTools = remember { mutableStateMapOf<String, Boolean>() }

    DisposableEffect(Unit) {
        onDispose { mediaPlayer?.release() }
    }

    /**
     * Google Play purchase through RevenueCat. The backend credits the wallet
     * when RevenueCat's webhook confirms the payment, so poll briefly for it.
     */
    fun buyOnPlay(productId: String) {
        val activity = context as? ComponentActivity
        if (activity == null || !Billing.isEnabled) {
            statusBanner = str(R.string.purchases_are_not_available_in_this)
            return
        }
        scope.launch {
            val before = walletBalanceInr
            try {
                Billing.purchase(activity, productId)
            } catch (e: Billing.BillingFailure) {
                statusBanner = e.message ?: str(R.string.the_purchase_did_not_complete)
                return@launch
            } catch (_: Exception) {
                statusBanner = str(R.string.the_purchase_did_not_complete_you)
                return@launch
            }
            statusBanner = str(R.string.payment_received_by_google_play_activating)
            repeat(15) {
                delay(2_000)
                try {
                    val w = ApiClient.onboardingApi.getMyWallet()
                    val bal = (w["call_balance_inr"] as? Number)?.toDouble()
                    val active = (w["deployment_status"] as? String) == "ACTIVE"
                    if (bal != null && bal != before) {
                        walletBalanceInr = bal
                        isStarterActive = active
                        statusBanner = str(R.string.done_your_plan_is_active)
                        return@launch
                    }
                } catch (_: Exception) {
                }
            }
            statusBanner = str(R.string.google_play_confirmed_the_payment_activation)
        }
    }

    fun playVoiceSample(assetPath: String, label: String) {
        try {
            mediaPlayer?.release()
            if (playingAudioAsset == assetPath) {
                playingAudioAsset = null
                return
            }
            val afd = context.assets.openFd(assetPath)
            val mp = MediaPlayer().apply {
                setDataSource(afd.fileDescriptor, afd.startOffset, afd.length)
                afd.close()
                prepare()
                setOnCompletionListener { playingAudioAsset = null }
                start()
            }
            mediaPlayer = mp
            playingAudioAsset = assetPath
            currentPose = "guidance"
            statusBanner = str(R.string.playing_a_sample_call, label)
        } catch (_: Exception) {
            playingAudioAsset = null
        }
    }

    fun buildFromUrl() {
        val url = targetUrl.trim().let { if (it.isNotEmpty() && !it.contains("://")) "https://$it" else it }
        if (url.isEmpty() || !android.util.Patterns.WEB_URL.matcher(url).matches()) {
            urlError = str(R.string.enter_a_link_like_yourshop_in)
            return
        }
        urlError = null
        scope.launch {
            isBusy = true
            currentPose = "scanning"
            statusBanner = str(R.string.reading_your_page_and_building_your)
            try {
                val res = ApiClient.onboardingApi.ingestUrl(
                    UrlIngestRequestDto(
                        url = url,
                        languages = listOf(selectedLanguage, "en-IN").distinct(),
                        mascot_id = selectedMascot,
                        category_id = selectedPack,
                    )
                )
                currentPose = "celebration"
                val biz = res["business_name"]?.toString()?.takeIf { it.isNotBlank() }
                if (biz != null) deployedBusiness = biz
                statusBanner = str(R.string.agent_ready_for, biz ?: str(R.string.your_business))
            } catch (e: Exception) {
                currentPose = "guidance"
                statusBanner = friendlyError(e, str(R.string.read_that_link))
            } finally {
                isBusy = false
            }
        }
    }

    fun buildFromDescription() {
        val text = description.trim()
        if (text.length < 20) {
            statusBanner = str(R.string.write_a_sentence_or_two_about)
            return
        }
        scope.launch {
            isBusy = true
            currentPose = "listening"
            statusBanner = str(R.string.building_your_agent_from_your_description)
            try {
                ApiClient.onboardingApi.ingestVoice(
                    VoiceNarrationRequestDto(
                        transcript = text,
                        language_code = selectedLanguage,
                        mascot_id = selectedMascot,
                    )
                )
                currentPose = "celebration"
                statusBanner = str(R.string.your_agent_is_ready_pick_a)
            } catch (e: Exception) {
                currentPose = "guidance"
                statusBanner = friendlyError(e, str(R.string.build_your_agent))
            }
            isBusy = false
        }
    }

    if (showDeleteConfirmDialog) {
        AlertDialog(
            onDismissRequest = { showDeleteConfirmDialog = false },
            title = { Text(str(R.string.delete_your_account)) },
            text = {
                Text(
                    str(R.string.this_permanently_deletes_your_profile_call)
                )
            },
            confirmButton = {
                PrimaryButton(
                    onClick = {
                        showDeleteConfirmDialog = false
                        scope.launch {
                            val actorId = TokenManager.getActorId()
                            if (actorId.isNullOrBlank()) {
                                statusBanner = str(R.string.sign_in_again_before_deleting_this)
                                return@launch
                            }
                            try {
                                ApiClient.onboardingApi.deleteAccount(actorId)
                                FirebaseSession.deleteLoginAndSignOut(context)
                                onAccountDeleted()
                            } catch (e: Exception) {
                                statusBanner = friendlyError(e, str(R.string.delete_the_account))
                            }
                        }
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = SangamCrimson),
                ) {
                    Text(str(R.string.delete_permanently))
                }
            },
            dismissButton = {
                SecondaryButton(onClick = { showDeleteConfirmDialog = false }) {
                    Text(str(R.string.cancel))
                }
            },
        )
    }

    if (showReportAiDialog) {
        AlertDialog(
            onDismissRequest = { showReportAiDialog = false },
            title = { Text(str(R.string.report_a_wrong_answer)) },
            text = {
                Text(str(R.string.tell_us_the_agent_quoted_a))
            },
            confirmButton = {
                PrimaryButton(
                    onClick = {
                        showReportAiDialog = false
                        scope.launch {
                            try {
                                ApiClient.onboardingApi.reportAiOutput(
                                    AiReportRequestDto(
                                        user_id = TokenManager.getActorId() ?: "",
                                        call_id = "call_live_verify",
                                        reason = "User flagged utterance for guardrail tuning",
                                    )
                                )
                                statusBanner = str(R.string.thanks_your_report_was_sent_for)
                            } catch (e: Exception) {
                                statusBanner = friendlyError(e, str(R.string.send_the_report))
                            }
                        }
                    },
                ) {
                    Text(str(R.string.send_report))
                }
            },
            dismissButton = {
                SecondaryButton(onClick = { showReportAiDialog = false }) {
                    Text(str(R.string.cancel))
                }
            },
        )
    }

    if (showForwardOffDialog) {
        AlertDialog(
            onDismissRequest = { showForwardOffDialog = false },
            title = { Text(str(R.string.turn_off_call_forwarding)) },
            text = {
                Text(str(R.string.your_phone_dials_002_which_turns))
            },
            confirmButton = {
                PrimaryButton(onClick = {
                    showForwardOffDialog = false
                    context.startActivity(Intent(Intent.ACTION_DIAL, Uri.parse("tel:" + Uri.encode("##002#"))))
                }) { Text(str(R.string.open_dialer)) }
            },
            dismissButton = {
                SecondaryButton(onClick = { showForwardOffDialog = false }) { Text(str(R.string.cancel)) }
            },
        )
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(str(R.string.voice_agent), maxLines = 1, overflow = TextOverflow.Ellipsis) },
                navigationIcon = { BackButton(onBack) },
                actions = {
                    IconButton(onClick = onOpenCallInbox) {
                        Icon(Icons.Default.Inbox, contentDescription = str(R.string.call_inbox))
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = SangamPureWhite),
            )
        },
        containerColor = SangamPureWhite,
    ) { padding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding),
            contentPadding = PaddingValues(start = 16.dp, end = 16.dp, top = 4.dp, bottom = 32.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            // Status line: the one place every action reports back, read aloud by TalkBack.
            item {
                Surface(
                    color = SangamAlabaster,
                    shape = RoundedCornerShape(12.dp),
                    border = BorderStroke(1.dp, SangamBorder),
                    modifier = Modifier
                        .fillMaxWidth()
                        .semantics { liveRegion = LiveRegionMode.Polite },
                ) {
                    Row(
                        modifier = Modifier.padding(12.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(12.dp),
                    ) {
                        MascotAvatar(mascotId = selectedMascot, pose = currentPose, sizeDp = 48)
                        Text(
                            statusBanner,
                            style = MaterialTheme.typography.bodyMedium,
                            color = SangamObsidian,
                            modifier = Modifier.weight(1f),
                        )
                        if (isBusy) {
                            CircularProgressIndicator(modifier = Modifier.size(20.dp), strokeWidth = 2.dp)
                        }
                    }
                }
            }

            // 1. Business details
            item {
                SetupSection(step = str(R.string.step_1), title = str(R.string.tell_us_about_your_business)) {
                    Text(str(R.string.your_agent_answers_in), style = MaterialTheme.typography.labelLarge, color = SangamZinc)
                    FlowRow(
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                        verticalArrangement = Arrangement.spacedBy(0.dp),
                    ) {
                        AGENT_LANGUAGES.forEach { (code, label) ->
                            FilterChip(
                                selected = selectedLanguage == code,
                                onClick = {
                                    selectedLanguage = code
                                    prefs.edit().putString("agent_language", code).apply()
                                },
                                label = { Text(label) },
                            )
                        }
                    }

                    OutlinedTextField(
                        value = targetUrl,
                        onValueChange = { targetUrl = it; urlError = null },
                        label = { Text(str(R.string.website_or_google_maps_link)) },
                        placeholder = { Text("yourshop.in") },
                        leadingIcon = { Icon(Icons.Default.Language, contentDescription = null) },
                        isError = urlError != null,
                        supportingText = urlError?.let { msg -> { Text(msg) } },
                        modifier = Modifier.fillMaxWidth(),
                        singleLine = true,
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri, imeAction = ImeAction.Go),
                        keyboardActions = KeyboardActions(onGo = { if (!isBusy) buildFromUrl() }),
                    )
                    PrimaryButton(
                        onClick = { buildFromUrl() },
                        enabled = !isBusy,
                        modifier = Modifier
                            .fillMaxWidth()
                            .heightIn(min = 48.dp),
                    ) {
                        Icon(Icons.Default.Bolt, contentDescription = null, modifier = Modifier.size(18.dp))
                        Spacer(Modifier.width(8.dp))
                        Text(str(R.string.build_my_agent_from_this_link))
                    }

                    Text(
                        str(R.string.no_website_describe_your_business_instead),
                        style = MaterialTheme.typography.bodyMedium,
                        color = SangamZinc,
                    )
                    OutlinedTextField(
                        value = description,
                        onValueChange = { description = it },
                        label = { Text(str(R.string.what_you_sell_timings_area)) },
                        modifier = Modifier.fillMaxWidth(),
                        minLines = 2,
                        keyboardOptions = KeyboardOptions(capitalization = KeyboardCapitalization.Sentences),
                    )
                    SecondaryButton(
                        onClick = { buildFromDescription() },
                        enabled = !isBusy,
                        modifier = Modifier
                            .fillMaxWidth()
                            .heightIn(min = 48.dp),
                    ) {
                        Text(str(R.string.build_from_my_description))
                    }

                    Text(str(R.string.type_of_business_optional), style = MaterialTheme.typography.labelLarge, color = SangamZinc)
                    // Wraps instead of scrolling sideways: half-cut chips hid that more existed.
                    FlowRow(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        VERTICAL_PACK_CHIPS.forEach { (packId, packTitle) ->
                            FilterChip(
                                selected = selectedPack == packId,
                                onClick = { selectedPack = if (selectedPack == packId) null else packId },
                                label = { Text(str(packTitle)) },
                            )
                        }
                    }
                }
            }

            // 2. Look and voice
            item {
                SetupSection(step = str(R.string.step_2), title = str(R.string.choose_how_your_agent_looks)) {
                    // Two per row: four in a row squeezes names into one letter per line on small phones.
                    AVAILABLE_MASCOTS.chunked(2).forEach { pair ->
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .height(IntrinsicSize.Min),
                            horizontalArrangement = Arrangement.spacedBy(8.dp),
                        ) {
                            pair.forEach { mascot ->
                                val selected = selectedMascot == mascot.id
                                OutlinedCard(
                                    modifier = Modifier
                                        .weight(1f)
                                        .fillMaxHeight()
                                        .selectable(
                                            selected = selected,
                                            role = Role.RadioButton,
                                            onClick = {
                                                selectedMascot = mascot.id
                                                currentPose = "idle"
                                                prefs.edit().putString("selected_mascot", mascot.id).apply()
                                            },
                                        ),
                                    colors = CardDefaults.outlinedCardColors(
                                        containerColor = if (selected) SangamObsidian else SangamAlabaster,
                                    ),
                                    border = BorderStroke(
                                        width = if (selected) 2.dp else 1.dp,
                                        color = if (selected) SangamObsidian else SangamBorder,
                                    ),
                                ) {
                                    Row(
                                        modifier = Modifier.padding(10.dp),
                                        verticalAlignment = Alignment.CenterVertically,
                                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                                    ) {
                                        MascotAvatar(mascotId = mascot.id, pose = "idle", sizeDp = 40)
                                        Text(
                                            mascot.name,
                                            fontWeight = FontWeight.Bold,
                                            color = if (selected) SangamPureWhite else SangamObsidian,
                                            maxLines = 2,
                                            modifier = Modifier.weight(1f),
                                        )
                                    }
                                }
                            }
                        }
                    }

                    Text(str(R.string.hear_a_sample_call), style = MaterialTheme.typography.labelLarge, color = SangamZinc)
                    FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        listOf(
                            Triple("audio/abhishek_kn.wav", str(R.string.kannada), "ಕನ್ನಡ"),
                            Triple("audio/abhishek_ml.wav", str(R.string.malayalam), "മലയാളം"),
                            Triple("audio/abhishek_te.wav", str(R.string.telugu), "తెలుగు"),
                        ).forEach { (asset, langName, nativeLabel) ->
                            val isPlaying = playingAudioAsset == asset
                            SecondaryButton(
                                onClick = { playVoiceSample(asset, langName) },
                                modifier = Modifier.semantics {
                                    contentDescription = if (isPlaying) str(R.string.stop_sample, langName) else str(R.string.play_sample, langName)
                                },
                            ) {
                                Icon(
                                    if (isPlaying) Icons.Default.Stop else Icons.AutoMirrored.Filled.VolumeUp,
                                    contentDescription = null,
                                    modifier = Modifier.size(16.dp),
                                )
                                Spacer(Modifier.width(6.dp))
                                Text(nativeLabel)
                            }
                        }
                    }
                }
            }

            // 3. Plan and payment
            item {
                SetupSection(step = str(R.string.step_3), title = str(R.string.pick_a_plan)) {
                    Text(
                        str(R.string.call_balance, "%,.2f".format(walletBalanceInr)),
                        style = MaterialTheme.typography.headlineMedium,
                    )
                    Text(
                        if (isStarterActive) str(R.string.plan_active) else str(R.string.no_active_plan),
                        style = MaterialTheme.typography.bodyMedium,
                        color = SangamZinc,
                        fontWeight = FontWeight.SemiBold,
                    )
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(IntrinsicSize.Min)
                            .horizontalScroll(rememberScrollState()),
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        plans.forEach { plan ->
                            val isSelected = plan.plan_id == selectedPlanId
                            OutlinedCard(
                                modifier = Modifier
                                    .widthIn(min = 150.dp, max = 180.dp)
                                    .fillMaxHeight()
                                    .selectable(
                                        selected = isSelected,
                                        role = Role.RadioButton,
                                        onClick = { selectedPlanId = plan.plan_id },
                                    ),
                                colors = CardDefaults.outlinedCardColors(
                                    containerColor = if (isSelected) SangamAlabaster else SangamPureWhite
                                ),
                                border = BorderStroke(
                                    width = if (isSelected) 2.dp else 1.dp,
                                    color = if (isSelected) SangamObsidian else SangamBorder
                                ),
                            ) {
                                Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                                    Text(plan.name, fontWeight = FontWeight.Bold, style = MaterialTheme.typography.bodyLarge)
                                    Text(
                                        if (plan.one_time) str(R.string.price_for_days, "%,d".format(plan.price_inr.toInt()), plan.validity_days) else str(R.string.price_per_month, "%,d".format(plan.price_inr.toInt())),
                                        style = MaterialTheme.typography.titleMedium,
                                        fontWeight = FontWeight.ExtraBold,
                                    )
                                    Text(str(R.string.about_minutes_of_calls, plan.included_minutes), style = MaterialTheme.typography.bodySmall, color = SangamZinc)
                                    Text(plan.audience, style = MaterialTheme.typography.bodySmall, color = SangamZinc)
                                }
                            }
                        }
                    }

                    val activePlan = plans.firstOrNull { it.plan_id == selectedPlanId } ?: plans.first()
                    Text(
                        str(
                            R.string.plan_breakdown,
                            activePlan.name,
                            "%,.2f".format(activePlan.price_inr),
                            "%,.2f".format(activePlan.gst_inr),
                            "%,.2f".format(activePlan.total_payable_inr),
                            activePlan.included_minutes,
                            "%.2f".format(activePlan.overage_rate_per_min_inr),
                        ),
                        style = MaterialTheme.typography.bodySmall,
                        color = SangamZinc,
                    )

                    PrimaryButton(
                        onClick = { buyOnPlay(selectedPlanId) },
                        enabled = Billing.isEnabled,
                        modifier = Modifier
                            .fillMaxWidth()
                            .heightIn(min = 48.dp),
                    ) {
                        Text(str(R.string.activate, activePlan.name), maxLines = 1, overflow = TextOverflow.Ellipsis)
                    }
                    SecondaryButton(
                        onClick = { buyOnPlay(Billing.TOPUP_PRODUCT) },
                        enabled = Billing.isEnabled,
                        modifier = Modifier
                            .fillMaxWidth()
                            .heightIn(min = 48.dp),
                    ) {
                        Text(str(R.string.add_500_call_balance))
                    }
                    if (Billing.isEnabled) {
                        Text(
                            str(R.string.paid_securely_through_google_play_prices),
                            style = MaterialTheme.typography.bodySmall,
                            color = SangamZinc,
                        )
                        FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            TextButton(onClick = {
                                scope.launch {
                                    statusBanner = try {
                                        Billing.restore()
                                        str(R.string.purchases_restored_your_plan_updates_within)
                                    } catch (e: Exception) {
                                        e.message ?: str(R.string.could_not_restore_purchases)
                                    }
                                }
                            }) { Text(str(R.string.restore_purchases)) }
                            TextButton(onClick = { Billing.openManageSubscriptions(context) }) {
                                Text(str(R.string.manage_subscription))
                            }
                        }
                    } else {
                        Text(
                            str(R.string.purchases_are_not_available_in_this_2),
                            style = MaterialTheme.typography.bodySmall,
                            color = SangamZinc,
                        )
                    }
                }
            }

            // 4. The number and call forwarding
            item {
                val phone = deployedPhone
                val dial = phone?.let(::dialable)
                OutlinedCard(
                    colors = CardDefaults.outlinedCardColors(containerColor = SangamObsidian),
                    border = BorderStroke(1.dp, SangamObsidian),
                ) {
                    Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.spacedBy(8.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Text(
                                str(R.string.step_4_your_agent_s_number),
                                style = MaterialTheme.typography.labelLarge,
                                color = Color(0xFFD4D4D8),
                                modifier = Modifier.weight(1f),
                            )
                            Surface(color = SangamPureWhite, shape = RoundedCornerShape(4.dp)) {
                                Text(
                                    if (isStarterActive) str(R.string.live) else str(R.string.not_live),
                                    color = SangamObsidian,
                                    style = MaterialTheme.typography.labelSmall,
                                    fontWeight = FontWeight.Bold,
                                    maxLines = 1,
                                    modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp),
                                )
                            }
                        }
                        Text(
                            phone ?: str(R.string.no_number_yet),
                            style = MaterialTheme.typography.headlineLarge,
                            color = SangamPureWhite,
                            fontFamily = if (phone != null) FontFamily.Monospace else FontFamily.Default,
                        )
                        Text(
                            if (phone == null) {
                                str(R.string.you_get_a_dedicated_91_number)
                            } else {
                                listOfNotNull(
                                    deployedBusiness,
                                    defaultLanguage?.let { code -> AGENT_LANGUAGES.firstOrNull { it.first == code }?.second ?: code },
                                ).joinToString(" · ")
                            },
                            style = MaterialTheme.typography.bodyMedium,
                            color = Color(0xFFD4D4D8),
                        )
                        if (dial != null) {
                            PrimaryButton(
                                onClick = { context.startActivity(Intent(Intent.ACTION_DIAL, Uri.parse("tel:$dial"))) },
                                colors = ButtonDefaults.buttonColors(
                                    containerColor = SangamPureWhite,
                                    contentColor = SangamObsidian,
                                ),
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .heightIn(min = 48.dp),
                            ) {
                                Icon(Icons.Default.Call, contentDescription = null, modifier = Modifier.size(18.dp))
                                Spacer(Modifier.width(8.dp))
                                Text(str(R.string.call_my_agent_to_test_it))
                            }
                            Text(
                                str(R.string.send_missed_calls_on_your_own),
                                style = MaterialTheme.typography.bodySmall,
                                color = Color(0xFFD4D4D8),
                            )
                            FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                SecondaryButton(
                                    onClick = {
                                        // *61* forwards unanswered calls only; busy and switched-off still ring the owner.
                                        val code = Uri.encode("*61*${dial.removePrefix("+91")}#")
                                        context.startActivity(Intent(Intent.ACTION_DIAL, Uri.parse("tel:$code")))
                                    },
                                    colors = ButtonDefaults.outlinedButtonColors(contentColor = SangamPureWhite),
                                    border = BorderStroke(1.dp, Color(0xFF71717A)),
                                ) {
                                    Icon(Icons.Default.PhoneForwarded, contentDescription = null, modifier = Modifier.size(18.dp))
                                    Spacer(Modifier.width(6.dp))
                                    Text(str(R.string.turn_on_forwarding))
                                }
                                SecondaryButton(
                                    onClick = { showForwardOffDialog = true },
                                    colors = ButtonDefaults.outlinedButtonColors(contentColor = SangamPureWhite),
                                    border = BorderStroke(1.dp, Color(0xFF71717A)),
                                ) {
                                    Text(str(R.string.turn_off))
                                }
                            }
                        }
                    }
                }
            }

            // 5. Connected apps
            item {
                SetupSection(step = str(R.string.optional), title = str(R.string.connect_your_apps)) {
                    Text(
                        str(R.string.after_each_call_your_agent_can),
                        style = MaterialTheme.typography.bodyMedium,
                        color = SangamZinc,
                    )
                    APP_INTEGRATIONS.forEach { (toolkit, name, blurb) ->
                        val enabled = connectedTools[toolkit] == true
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .toggleable(
                                    value = enabled,
                                    role = Role.Switch,
                                    onValueChange = { checked ->
                                        connectedTools[toolkit] = checked
                                        scope.launch {
                                            try {
                                                ApiClient.onboardingApi.connectComposioTool(
                                                    ComposioConnectRequestDto(
                                                        user_id = TokenManager.getActorId() ?: "",
                                                        toolkit = toolkit,
                                                    )
                                                )
                                            } catch (e: Exception) {
                                                connectedTools[toolkit] = !checked
                                                statusBanner = friendlyError(e, str(R.string.connect, name))
                                            }
                                        }
                                    },
                                )
                                .padding(vertical = 6.dp),
                            horizontalArrangement = Arrangement.spacedBy(12.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Column(Modifier.weight(1f)) {
                                Text(name, fontWeight = FontWeight.SemiBold)
                                Text(str(blurb), style = MaterialTheme.typography.bodySmall, color = SangamZinc)
                            }
                            // The whole row toggles, so the switch itself is not a separate touch target.
                            Switch(checked = enabled, onCheckedChange = null)
                        }
                    }
                }
            }

            // 6. Referral
            if (referralCode.isNotBlank()) {
                item {
                    SetupSection(step = str(R.string.refer_and_earn), title = str(R.string.give_100_get_100)) {
                        Text(
                            str(R.string.your_code, referralCode),
                            style = MaterialTheme.typography.bodyLarge,
                            fontFamily = FontFamily.Monospace,
                        )
                        SecondaryButton(
                            onClick = {
                                val line = deployedPhone?.let { str(R.string.call_it_on, it) }.orEmpty()
                                val shareText = str(R.string.namaste_my_business_now_has_a, line, referralCode) +
                                    "https://sangamitra.in/r/$referralCode"
                                val sendIntent = Intent(Intent.ACTION_SEND).apply {
                                    type = "text/plain"
                                    putExtra(Intent.EXTRA_TEXT, shareText)
                                }
                                context.startActivity(Intent.createChooser(sendIntent, str(R.string.share_your_code)))
                            },
                            modifier = Modifier.heightIn(min = 48.dp),
                        ) {
                            Icon(Icons.Default.Share, contentDescription = null, modifier = Modifier.size(16.dp))
                            Spacer(Modifier.width(6.dp))
                            Text(str(R.string.share_code))
                        }
                    }
                }
            }

            // 7. Account and safety (Play policy: report AI output, delete account)
            item {
                SetupSection(step = str(R.string.account), title = str(R.string.safety_and_privacy)) {
                    SecondaryButton(
                        onClick = { showReportAiDialog = true },
                        modifier = Modifier
                            .fillMaxWidth()
                            .heightIn(min = 48.dp),
                    ) {
                        Icon(Icons.Default.Flag, contentDescription = null, modifier = Modifier.size(16.dp))
                        Spacer(Modifier.width(6.dp))
                        Text(str(R.string.report_a_wrong_answer))
                    }
                    SecondaryButton(
                        onClick = { showDeleteConfirmDialog = true },
                        colors = ButtonDefaults.outlinedButtonColors(contentColor = SangamCrimson),
                        modifier = Modifier
                            .fillMaxWidth()
                            .heightIn(min = 48.dp),
                    ) {
                        Icon(Icons.Default.DeleteOutline, contentDescription = null, modifier = Modifier.size(16.dp))
                        Spacer(Modifier.width(6.dp))
                        Text(str(R.string.delete_account))
                    }
                }
            }
        }
    }
}

/** A titled card. The step label is a heading for TalkBack's heading navigation. */
@Composable
private fun SetupSection(step: String, title: String, content: @Composable ColumnScope.() -> Unit) {
    OutlinedCard(
        colors = CardDefaults.outlinedCardColors(containerColor = SangamPureWhite),
        border = BorderStroke(1.dp, SangamBorder),
    ) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Column(Modifier.semantics(mergeDescendants = true) { heading() }) {
                Text(step.uppercase(), style = MaterialTheme.typography.labelLarge, color = SangamZinc)
                Text(title, style = MaterialTheme.typography.titleLarge)
            }
            content()
        }
    }
}
