package com.sangam.app.ui.screens

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
    "b2b_minerals" to "B2B Minerals & Factory",
    "csc_meeseva" to "CSC / MeeSeva Kendra",
    "dental_clinic" to "Dental & OPD Clinic",
    "real_estate" to "Real Estate & Plots",
    "restaurant_cloud" to "Restaurant & Catering",
    "salon_bridal" to "Salon & Bridal Studio",
    "auto_service" to "Auto Service Centre",
    "ca_tax_legal" to "CA, GST & Legal Office",
    "hotel_resort" to "Hotel & Homestay",
    "hardware_tiles" to "Hardware & Tiles Wholesale",
    "jewellery_bullion" to "Jewellery Showroom",
    "personal_vip" to "VIP Personal Secretary",
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
    Triple("WHATSAPP", "WhatsApp", "Send the caller your catalogue, quote or location"),
    Triple("GOOGLESHEETS", "Google Sheets", "Add every caller as a new row"),
    Triple("GOOGLECALENDAR", "Google Calendar", "Book visits and appointments"),
    Triple("TALLY_PRIME", "Tally Prime", "Create a draft sales order"),
    Triple("INDIAMART", "IndiaMART", "Call new IndiaMART leads within a minute"),
    Triple("ZOHO_CRM", "Zoho CRM", "Save the lead and call notes"),
    Triple("SHOPIFY", "Shopify", "Confirm cash-on-delivery orders by phone"),
    Triple("SHIPROCKET", "Shiprocket", "Tell callers where their parcel is"),
    Triple("GMAIL", "Gmail", "Email you a summary after each call"),
    Triple("TELEGRAM", "Telegram", "Message you when a hot lead calls"),
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
        mutableStateOf("Paste your website or Google Maps link, or describe your business, and we'll build your agent.")
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
                PlanDto("pilot", "7-Day Live Pilot", "Try it on a real number", 7, true, 799.0, 143.82, 942.82, 85, 651.50),
                PlanDto("personal", "Mitra Personal", "Individuals & Creators", 30, false, 999.0, 179.82, 1178.82, 113, 851.50),
                PlanDto("vyapar", "Vyapar Starter", "Shops, Clinics & SMBs", 30, false, 2499.0, 449.82, 2948.82, 313, 2351.50),
                PlanDto("udyog", "Udyog B2B Pro", "Manufacturing & B2B Desks", 30, false, 4999.0, 899.82, 5898.82, 646, 4851.50),
                PlanDto("enterprise", "Enterprise", "Multi-Branch & High Volume", 30, false, 11999.0, 2159.82, 14158.82, 1579, 11851.50),
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
            statusBanner = friendlyError(e, "load your agent")
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
            statusBanner = "Purchases are not available in this version of the app. Update it from Google Play."
            return
        }
        scope.launch {
            val before = walletBalanceInr
            try {
                Billing.purchase(activity, productId)
            } catch (e: Billing.BillingFailure) {
                statusBanner = e.message ?: "The purchase did not complete."
                return@launch
            } catch (_: Exception) {
                statusBanner = "The purchase did not complete. You were not charged."
                return@launch
            }
            statusBanner = "Payment received by Google Play. Activating..."
            repeat(15) {
                delay(2_000)
                try {
                    val w = ApiClient.onboardingApi.getMyWallet()
                    val bal = (w["call_balance_inr"] as? Number)?.toDouble()
                    val active = (w["deployment_status"] as? String) == "ACTIVE"
                    if (bal != null && bal != before) {
                        walletBalanceInr = bal
                        isStarterActive = active
                        statusBanner = "Done. Your plan is active."
                        return@launch
                    }
                } catch (_: Exception) {
                }
            }
            statusBanner = "Google Play confirmed the payment. Activation can take a minute; reopen this screen to check."
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
            statusBanner = "Playing a $label sample call."
        } catch (_: Exception) {
            playingAudioAsset = null
        }
    }

    fun buildFromUrl() {
        val url = targetUrl.trim().let { if (it.isNotEmpty() && !it.contains("://")) "https://$it" else it }
        if (url.isEmpty() || !android.util.Patterns.WEB_URL.matcher(url).matches()) {
            urlError = "Enter a link like yourshop.in or a Google Maps link."
            return
        }
        urlError = null
        scope.launch {
            isBusy = true
            currentPose = "scanning"
            statusBanner = "Reading your page and building your agent. This takes about a minute."
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
                statusBanner = "Your agent for ${biz ?: "your business"} is ready. Pick a plan below to get your number."
            } catch (e: Exception) {
                currentPose = "guidance"
                statusBanner = friendlyError(e, "read that link")
            } finally {
                isBusy = false
            }
        }
    }

    fun buildFromDescription() {
        val text = description.trim()
        if (text.length < 20) {
            statusBanner = "Write a sentence or two about what you sell, your timings and your area."
            return
        }
        scope.launch {
            isBusy = true
            currentPose = "listening"
            statusBanner = "Building your agent from your description..."
            try {
                ApiClient.onboardingApi.ingestVoice(
                    VoiceNarrationRequestDto(
                        transcript = text,
                        language_code = selectedLanguage,
                        mascot_id = selectedMascot,
                    )
                )
                currentPose = "celebration"
                statusBanner = "Your agent is ready. Pick a plan below to get your number."
            } catch (e: Exception) {
                currentPose = "guidance"
                statusBanner = friendlyError(e, "build your agent")
            }
            isBusy = false
        }
    }

    if (showDeleteConfirmDialog) {
        AlertDialog(
            onDismissRequest = { showDeleteConfirmDialog = false },
            title = { Text("Delete your account?") },
            text = {
                Text(
                    "This permanently deletes your profile, call recordings, call balance and connected apps, " +
                        "and releases your agent's phone number. This cannot be undone."
                )
            },
            confirmButton = {
                Button(
                    onClick = {
                        showDeleteConfirmDialog = false
                        scope.launch {
                            val actorId = TokenManager.getActorId()
                            if (actorId.isNullOrBlank()) {
                                statusBanner = "Sign in again before deleting this account."
                                return@launch
                            }
                            try {
                                ApiClient.onboardingApi.deleteAccount(actorId)
                                FirebaseSession.deleteLoginAndSignOut(context)
                                onAccountDeleted()
                            } catch (e: Exception) {
                                statusBanner = friendlyError(e, "delete the account")
                            }
                        }
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = SangamCrimson),
                ) {
                    Text("Delete permanently")
                }
            },
            dismissButton = {
                OutlinedButton(onClick = { showDeleteConfirmDialog = false }) {
                    Text("Cancel")
                }
            },
        )
    }

    if (showReportAiDialog) {
        AlertDialog(
            onDismissRequest = { showReportAiDialog = false },
            title = { Text("Report a wrong answer") },
            text = {
                Text("Tell us the agent quoted a wrong price, switched to the wrong language, or said something inappropriate. Our team reviews every report.")
            },
            confirmButton = {
                Button(
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
                                statusBanner = "Thanks. Your report was sent for review."
                            } catch (e: Exception) {
                                statusBanner = friendlyError(e, "send the report")
                            }
                        }
                    },
                ) {
                    Text("Send report")
                }
            },
            dismissButton = {
                OutlinedButton(onClick = { showReportAiDialog = false }) {
                    Text("Cancel")
                }
            },
        )
    }

    if (showForwardOffDialog) {
        AlertDialog(
            onDismissRequest = { showForwardOffDialog = false },
            title = { Text("Turn off call forwarding?") },
            text = {
                Text("Your phone dials ##002#, which turns off all call forwarding on this SIM, including any you set up before Sangamitra. Missed calls will no longer reach your agent.")
            },
            confirmButton = {
                Button(onClick = {
                    showForwardOffDialog = false
                    context.startActivity(Intent(Intent.ACTION_DIAL, Uri.parse("tel:" + Uri.encode("##002#"))))
                }) { Text("Open dialer") }
            },
            dismissButton = {
                OutlinedButton(onClick = { showForwardOffDialog = false }) { Text("Cancel") }
            },
        )
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Voice agent", maxLines = 1, overflow = TextOverflow.Ellipsis) },
                navigationIcon = { BackButton(onBack) },
                actions = {
                    IconButton(onClick = onOpenCallInbox) {
                        Icon(Icons.Default.Inbox, contentDescription = "Call inbox")
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
                SetupSection(step = "Step 1", title = "Tell us about your business") {
                    Text("Your agent answers in", style = MaterialTheme.typography.labelLarge, color = SangamZinc)
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
                        label = { Text("Website or Google Maps link") },
                        placeholder = { Text("yourshop.in") },
                        leadingIcon = { Icon(Icons.Default.Language, contentDescription = null) },
                        isError = urlError != null,
                        supportingText = urlError?.let { msg -> { Text(msg) } },
                        modifier = Modifier.fillMaxWidth(),
                        singleLine = true,
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri, imeAction = ImeAction.Go),
                        keyboardActions = KeyboardActions(onGo = { if (!isBusy) buildFromUrl() }),
                    )
                    Button(
                        onClick = { buildFromUrl() },
                        enabled = !isBusy,
                        modifier = Modifier
                            .fillMaxWidth()
                            .heightIn(min = 48.dp),
                    ) {
                        Icon(Icons.Default.Bolt, contentDescription = null, modifier = Modifier.size(18.dp))
                        Spacer(Modifier.width(8.dp))
                        Text("Build my agent from this link")
                    }

                    Text(
                        "No website? Describe your business instead.",
                        style = MaterialTheme.typography.bodyMedium,
                        color = SangamZinc,
                    )
                    OutlinedTextField(
                        value = description,
                        onValueChange = { description = it },
                        label = { Text("What you sell, timings, area") },
                        modifier = Modifier.fillMaxWidth(),
                        minLines = 2,
                        keyboardOptions = KeyboardOptions(capitalization = KeyboardCapitalization.Sentences),
                    )
                    OutlinedButton(
                        onClick = { buildFromDescription() },
                        enabled = !isBusy,
                        modifier = Modifier
                            .fillMaxWidth()
                            .heightIn(min = 48.dp),
                    ) {
                        Text("Build from my description")
                    }

                    Text("Type of business (optional)", style = MaterialTheme.typography.labelLarge, color = SangamZinc)
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .horizontalScroll(rememberScrollState()),
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        VERTICAL_PACK_CHIPS.forEach { (packId, packTitle) ->
                            FilterChip(
                                selected = selectedPack == packId,
                                onClick = { selectedPack = if (selectedPack == packId) null else packId },
                                label = { Text(packTitle) },
                            )
                        }
                    }
                }
            }

            // 2. Look and voice
            item {
                SetupSection(step = "Step 2", title = "Choose how your agent looks") {
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

                    Text("Hear a sample call", style = MaterialTheme.typography.labelLarge, color = SangamZinc)
                    FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        listOf(
                            Triple("audio/abhishek_kn.wav", "Kannada", "ಕನ್ನಡ"),
                            Triple("audio/abhishek_ml.wav", "Malayalam", "മലയാളം"),
                            Triple("audio/abhishek_te.wav", "Telugu", "తెలుగు"),
                        ).forEach { (asset, langName, nativeLabel) ->
                            val isPlaying = playingAudioAsset == asset
                            OutlinedButton(
                                onClick = { playVoiceSample(asset, langName) },
                                modifier = Modifier.semantics {
                                    contentDescription = (if (isPlaying) "Stop " else "Play ") + "$langName sample"
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
                SetupSection(step = "Step 3", title = "Pick a plan") {
                    Text(
                        "Call balance: ₹${"%,.2f".format(walletBalanceInr)}",
                        style = MaterialTheme.typography.headlineMedium,
                    )
                    Text(
                        if (isStarterActive) "Plan active" else "No active plan",
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
                                        "₹${"%,d".format(plan.price_inr.toInt())}${if (plan.one_time) " for ${plan.validity_days} days" else " / month"}",
                                        style = MaterialTheme.typography.titleMedium,
                                        fontWeight = FontWeight.ExtraBold,
                                    )
                                    Text("About ${plan.included_minutes} minutes of calls", style = MaterialTheme.typography.bodySmall, color = SangamZinc)
                                    Text(plan.audience, style = MaterialTheme.typography.bodySmall, color = SangamZinc)
                                }
                            }
                        }
                    }

                    val activePlan = plans.firstOrNull { it.plan_id == selectedPlanId } ?: plans.first()
                    Text(
                        "${activePlan.name}: ₹${"%,.2f".format(activePlan.price_inr)} + 18% GST (₹${"%,.2f".format(activePlan.gst_inr)}) = " +
                            "₹${"%,.2f".format(activePlan.total_payable_inr)}. Includes a dedicated +91 number and about " +
                            "${activePlan.included_minutes} minutes. Extra minutes ₹${"%.2f".format(activePlan.overage_rate_per_min_inr)} each.",
                        style = MaterialTheme.typography.bodySmall,
                        color = SangamZinc,
                    )

                    Button(
                        onClick = { buyOnPlay(selectedPlanId) },
                        enabled = Billing.isEnabled,
                        modifier = Modifier
                            .fillMaxWidth()
                            .heightIn(min = 48.dp),
                    ) {
                        Text("Activate ${activePlan.name}", maxLines = 1, overflow = TextOverflow.Ellipsis)
                    }
                    OutlinedButton(
                        onClick = { buyOnPlay(Billing.TOPUP_PRODUCT) },
                        enabled = Billing.isEnabled,
                        modifier = Modifier
                            .fillMaxWidth()
                            .heightIn(min = 48.dp),
                    ) {
                        Text("Add ₹500 call balance")
                    }
                    if (Billing.isEnabled) {
                        Text(
                            "Paid securely through Google Play. Prices on the Google Play sheet include taxes.",
                            style = MaterialTheme.typography.bodySmall,
                            color = SangamZinc,
                        )
                        FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            TextButton(onClick = {
                                scope.launch {
                                    statusBanner = try {
                                        Billing.restore()
                                        "Purchases restored. Your plan updates within a minute."
                                    } catch (e: Exception) {
                                        e.message ?: "Could not restore purchases."
                                    }
                                }
                            }) { Text("Restore purchases") }
                            TextButton(onClick = { Billing.openManageSubscriptions(context) }) {
                                Text("Manage subscription")
                            }
                        }
                    } else {
                        Text(
                            "Purchases are not available in this version of the app. Install Sangamitra from Google Play to buy a plan.",
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
                                "Step 4 · Your agent's number",
                                style = MaterialTheme.typography.labelLarge,
                                color = Color(0xFFD4D4D8),
                                modifier = Modifier.weight(1f),
                            )
                            Surface(color = SangamPureWhite, shape = RoundedCornerShape(4.dp)) {
                                Text(
                                    if (isStarterActive) "LIVE" else "NOT LIVE",
                                    color = SangamObsidian,
                                    style = MaterialTheme.typography.labelSmall,
                                    fontWeight = FontWeight.Bold,
                                    maxLines = 1,
                                    modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp),
                                )
                            }
                        }
                        Text(
                            phone ?: "No number yet",
                            style = MaterialTheme.typography.headlineLarge,
                            color = SangamPureWhite,
                            fontFamily = if (phone != null) FontFamily.Monospace else FontFamily.Default,
                        )
                        Text(
                            if (phone == null) {
                                "You get a dedicated +91 number when a plan is active."
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
                            Button(
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
                                Text("Call my agent to test it")
                            }
                            Text(
                                "Send missed calls on your own SIM to your agent:",
                                style = MaterialTheme.typography.bodySmall,
                                color = Color(0xFFD4D4D8),
                            )
                            FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                OutlinedButton(
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
                                    Text("Turn on forwarding")
                                }
                                OutlinedButton(
                                    onClick = { showForwardOffDialog = true },
                                    colors = ButtonDefaults.outlinedButtonColors(contentColor = SangamPureWhite),
                                    border = BorderStroke(1.dp, Color(0xFF71717A)),
                                ) {
                                    Text("Turn off")
                                }
                            }
                        }
                    }
                }
            }

            // 5. Connected apps
            item {
                SetupSection(step = "Optional", title = "Connect your apps") {
                    Text(
                        "After each call, your agent can update these for you.",
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
                                                statusBanner = friendlyError(e, "connect $name")
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
                                Text(blurb, style = MaterialTheme.typography.bodySmall, color = SangamZinc)
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
                    SetupSection(step = "Refer and earn", title = "Give ₹100, get ₹100") {
                        Text(
                            "Your code: $referralCode",
                            style = MaterialTheme.typography.bodyLarge,
                            fontFamily = FontFamily.Monospace,
                        )
                        OutlinedButton(
                            onClick = {
                                val line = deployedPhone?.let { " (call it on $it)" }.orEmpty()
                                val shareText = "Namaste! My business now has a 24/7 AI phone agent from Sangamitra$line. " +
                                    "Set up yours in a minute and get ₹100 free call balance with code $referralCode: " +
                                    "https://sangamitra.in/r/$referralCode"
                                val sendIntent = Intent(Intent.ACTION_SEND).apply {
                                    type = "text/plain"
                                    putExtra(Intent.EXTRA_TEXT, shareText)
                                }
                                context.startActivity(Intent.createChooser(sendIntent, "Share your code"))
                            },
                            modifier = Modifier.heightIn(min = 48.dp),
                        ) {
                            Icon(Icons.Default.Share, contentDescription = null, modifier = Modifier.size(16.dp))
                            Spacer(Modifier.width(6.dp))
                            Text("Share code")
                        }
                    }
                }
            }

            // 7. Account and safety (Play policy: report AI output, delete account)
            item {
                SetupSection(step = "Account", title = "Safety and privacy") {
                    OutlinedButton(
                        onClick = { showReportAiDialog = true },
                        modifier = Modifier
                            .fillMaxWidth()
                            .heightIn(min = 48.dp),
                    ) {
                        Icon(Icons.Default.Flag, contentDescription = null, modifier = Modifier.size(16.dp))
                        Spacer(Modifier.width(6.dp))
                        Text("Report a wrong answer")
                    }
                    OutlinedButton(
                        onClick = { showDeleteConfirmDialog = true },
                        colors = ButtonDefaults.outlinedButtonColors(contentColor = SangamCrimson),
                        modifier = Modifier
                            .fillMaxWidth()
                            .heightIn(min = 48.dp),
                    ) {
                        Icon(Icons.Default.DeleteOutline, contentDescription = null, modifier = Modifier.size(16.dp))
                        Spacer(Modifier.width(6.dp))
                        Text("Delete account")
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
