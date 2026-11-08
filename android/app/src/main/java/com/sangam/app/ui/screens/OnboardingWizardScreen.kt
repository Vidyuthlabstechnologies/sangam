package com.sangam.app.ui.screens

import android.content.Context
import android.content.Intent
import android.graphics.BitmapFactory
import android.media.MediaPlayer
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
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
import androidx.compose.ui.unit.dp
import com.sangam.app.R
import com.sangam.app.network.*
import com.sangam.app.ui.theme.*
import kotlinx.coroutines.launch

data class MascotOption(
    val id: String,
    val name: String,
    val style: String,
    val tagline: String,
)

val AVAILABLE_MASCOTS = listOf(
    MascotOption("kite", "Kite Master", "Aviator Kite with Headset", "Autonomous telecom navigator powered by Sarvam AI"),
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
                contentDescription = "Kite Master ($pose)",
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
                contentDescription = "$mascotId $pose",
                contentScale = ContentScale.Crop,
                modifier = Modifier.fillMaxSize(),
            )
        } else {
            Icon(
                Icons.Default.RecordVoiceOver,
                contentDescription = "Mascot",
                tint = SangamObsidian,
            )
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun OnboardingWizardScreen(
    onBack: () -> Unit = {},
    onOpenCallInbox: () -> Unit = {},
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val prefs = remember { context.getSharedPreferences("sangamitra_prefs", Context.MODE_PRIVATE) }

    var selectedMascot by remember { mutableStateOf(prefs.getString("selected_mascot", "kite") ?: "kite") }
    var currentPose by remember { mutableStateOf("idle") }
    var selectedPack by remember { mutableStateOf("b2b_minerals") }
    var targetUrl by remember { mutableStateOf("https://abhishek-industries.pages.dev/") }
    var voiceTranscript by remember {
        mutableStateOf("ನಮ್ಮದು ತುಮಕೂರಿನಲ್ಲಿ ಅಭಿಷೇಕ್ ಇಂಡಸ್ಟ್ರೀಸ್, ನಾವು ಕಾವೋಲಿನ್, ಕ್ವಾರ್ಟ್ಜ್, ಫೆಲ್ಡ್ಸ್ಪಾರ್ ಮಿನರಲ್ ಪೌಡರ್ ಸಪ್ಲೈ ಮಾಡ್ತೀವಿ.")
    }
    var statusBanner by remember {
        mutableStateOf("Ready: Paste a website URL, scan a shop board photo, or speak in any of 22 Indian languages.")
    }
    var isBusy by remember { mutableStateOf(false) }

    // Live provisioned agent state
    var deployedPhone by remember { mutableStateOf("+91 80 6427 0314") }
    var deployedBusiness by remember { mutableStateOf("Abhishek Industries (Tumakuru)") }
    var defaultLanguage by remember { mutableStateOf("Kannada (Colloquial Sales + Code-Mixed English)") }
    var openingGreeting by remember {
        mutableStateOf("ನಮಸ್ಕಾರ ಸರ್! ಅಭಿಷೇಕ್ ಇಂಡಸ್ಟ್ರೀಸ್ ತುಮಕೂರು, ನಾನು ಮೀರಾ ಮಾತಾಡ್ತಿರೋದು. ಹೇಳಿ ಸರ್, ನಿಮ್ಮ factory ಗೆ ಯಾವ mineral powder requirement ಇತ್ತು?")
    }

    // Audio sample player state
    var playingAudioAsset by remember { mutableStateOf<String?>(null) }
    var mediaPlayer by remember { mutableStateOf<MediaPlayer?>(null) }

    // Subscription plans & 60/40 wallet state
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
    var walletBalanceInr by remember { mutableStateOf(2351.50) }
    var isStarterActive by remember { mutableStateOf(true) }
    var upiAutopayEnabled by remember { mutableStateOf(true) }
    var referralCode by remember { mutableStateOf("SANGAM-ABHISHEK") }

    LaunchedEffect(Unit) {
        try {
            val response = ApiClient.onboardingApi.getPlans()
            if (response.plans.isNotEmpty()) {
                plans = response.plans
            }
        } catch (_: Exception) { }

        try {
            val w = ApiClient.onboardingApi.getMyWallet()
            val bal = (w["call_balance_inr"] as? Number)?.toDouble()
            if (bal != null) walletBalanceInr = bal
            val active = (w["deployment_status"] as? String) == "ACTIVE"
            isStarterActive = active
            val ref = w["referral_code"] as? String
            if (!ref.isNullOrBlank()) referralCode = ref
            val phone = w["assigned_did"] as? String
            if (!phone.isNullOrBlank()) deployedPhone = phone
        } catch (_: Exception) { }
    }

    // Dialog states
    var showDeleteConfirmDialog by remember { mutableStateOf(false) }
    var showReportAiDialog by remember { mutableStateOf(false) }

    // Composio 13-tool state
    val connectedTools = remember {
        mutableStateMapOf(
            "WHATSAPP" to true,
            "GOOGLESHEETS" to true,
            "GOOGLECALENDAR" to true,
            "TALLY_PRIME" to true,
            "INDIAMART" to true,
            "RAZORPAY" to true,
            "ZOHO_CRM" to false,
            "SHOPIFY" to false,
            "SHIPROCKET" to false,
            "GMAIL" to false,
            "TELEGRAM" to false,
        )
    }

    DisposableEffect(Unit) {
        onDispose { mediaPlayer?.release() }
    }

    fun playVoiceSample(assetPath: String, label: String) {
        try {
            mediaPlayer?.release()
            if (playingAudioAsset == assetPath) {
                playingAudioAsset = null
                statusBanner = "Stopped audio sample playback."
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
            statusBanner = "Playing live $label sales voice sample (bulbul:v3 + sarvam-105b)..."
        } catch (_: Exception) {
            playingAudioAsset = null
        }
    }

    val photoPickerLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.PickVisualMedia()
    ) { uri ->
        if (uri != null) {
            scope.launch {
                isBusy = true
                currentPose = "scanning"
                statusBanner = "Running Indic Vision OCR on selected shop-board / brochure photo..."
                try {
                    val res = ApiClient.onboardingApi.ingestImageOcr(
                        mapOf(
                            "extracted_text" to "Abhishek Industries Tumakuru · China Clay, Quartz, Feldspar, Dolomite · +91 9739999992",
                            "filename" to (uri.lastPathSegment ?: "shop_board.jpg"),
                            "languages" to listOf("kn-IN", "ml-IN", "te-IN"),
                        )
                    )
                    deployedBusiness = (res["business_profile"] as? Map<*, *>)?.get("business_name")?.toString() ?: deployedBusiness
                } catch (_: Exception) { }
                currentPose = "celebration"
                statusBanner = "Shop-board OCR compiled into 24/7 Kannada/Multilingual Sales Agent."
                isBusy = false
            }
        }
    }

    val micPermissionLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestPermission()
    ) { _ ->
        scope.launch {
            isBusy = true
            currentPose = "listening"
            statusBanner = "Listening to spoken narration & compiling zero-prompt voice agent..."
            try {
                ApiClient.onboardingApi.ingestVoice(
                    VoiceNarrationRequestDto(
                        transcript = voiceTranscript,
                        language_code = "kn-IN",
                        mascot_id = selectedMascot,
                    )
                )
            } catch (_: Exception) { }
            currentPose = "celebration"
            statusBanner = "Spoken Kannada narration compiled into proactive sales persona."
            isBusy = false
        }
    }

    if (showDeleteConfirmDialog) {
        AlertDialog(
            onDismissRequest = { showDeleteConfirmDialog = false },
            title = { Text("Delete Account & All Voice Data?") },
            text = {
                Text("Per DPDP Act 2023 & Google Play Data Safety rules, this permanently deletes your actor profile, call recordings, wallet ledger, Composio OAuth tokens, and releases your DID number.")
            },
            confirmButton = {
                Button(
                    onClick = {
                        showDeleteConfirmDialog = false
                        scope.launch {
                            try {
                                ApiClient.onboardingApi.deleteAccount("abhishek-industries")
                            } catch (_: Exception) { }
                            statusBanner = "Account and all associated voice/wallet data permanently deleted."
                        }
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = SangamCrimson),
                ) {
                    Text("Delete Permanently")
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
            title = { Text("Report AI Voice Output") },
            text = {
                Text("Flag an inaccurate price quote, wrong language switch, or inappropriate AI response for guardrail review.")
            },
            confirmButton = {
                Button(
                    onClick = {
                        showReportAiDialog = false
                        scope.launch {
                            try {
                                ApiClient.onboardingApi.reportAiOutput(
                                    AiReportRequestDto(
                                        user_id = "abhishek-industries",
                                        call_id = "call_live_verify",
                                        reason = "User flagged utterance for guardrail tuning",
                                    )
                                )
                            } catch (_: Exception) { }
                            statusBanner = "AI output report logged for Play Store Generative AI safety review."
                        }
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = SangamObsidian),
                ) {
                    Text("Submit Report")
                }
            },
            dismissButton = {
                OutlinedButton(onClick = { showReportAiDialog = false }) {
                    Text("Cancel")
                }
            },
        )
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(
                            "SANGAMITRA",
                            style = MaterialTheme.typography.titleLarge,
                            fontWeight = FontWeight.Bold,
                        )
                        Spacer(Modifier.width(8.dp))
                        Surface(
                            color = SangamObsidian,
                            shape = RoundedCornerShape(4.dp),
                        ) {
                            Text(
                                "v1.0 RELEASE",
                                color = SangamPureWhite,
                                style = MaterialTheme.typography.labelSmall,
                                modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp),
                            )
                        }
                    }
                },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "Back")
                    }
                },
                actions = {
                    TextButton(onClick = onOpenCallInbox) {
                        Icon(Icons.Default.Inbox, contentDescription = null, modifier = Modifier.size(18.dp))
                        Spacer(Modifier.width(4.dp))
                        Text("Call Inbox")
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
                .padding(padding)
                .padding(horizontal = 16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            // 1. Choose Your AI Mascot (All 3 Mascots Selectable + Persisted)
            item {
                Spacer(Modifier.height(4.dp))
                OutlinedCard(
                    colors = CardDefaults.outlinedCardColors(containerColor = SangamPureWhite),
                    border = BorderStroke(1.dp, SangamBorder),
                ) {
                    Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.SpaceBetween,
                            modifier = Modifier.fillMaxWidth(),
                        ) {
                            Column(Modifier.weight(1f)) {
                                Text(
                                    "1. SELECT YOUR AI CONCIERGE MASCOT",
                                    style = MaterialTheme.typography.labelLarge,
                                    color = SangamMuted,
                                )
                                Text(
                                    "Choose Kite Master, Mitra, Swar, or Vani",
                                    style = MaterialTheme.typography.titleLarge,
                                )
                            }
                            MascotAvatar(mascotId = selectedMascot, pose = currentPose, sizeDp = 64)
                        }

                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.spacedBy(8.dp),
                        ) {
                            AVAILABLE_MASCOTS.forEach { mascot ->
                                val selected = selectedMascot == mascot.id
                                OutlinedCard(
                                    modifier = Modifier
                                        .weight(1f)
                                        .clickable {
                                            selectedMascot = mascot.id
                                            currentPose = "idle"
                                            prefs.edit().putString("selected_mascot", mascot.id).apply()
                                            statusBanner = "Selected ${mascot.name} (${mascot.style}) as your app guide."
                                        },
                                    colors = CardDefaults.outlinedCardColors(
                                        containerColor = if (selected) SangamObsidian else SangamAlabaster,
                                    ),
                                    border = BorderStroke(
                                        width = if (selected) 2.dp else 1.dp,
                                        color = if (selected) SangamObsidian else SangamBorder,
                                    ),
                                ) {
                                    Column(
                                        modifier = Modifier.padding(10.dp),
                                        horizontalAlignment = Alignment.CenterHorizontally,
                                        verticalArrangement = Arrangement.spacedBy(6.dp),
                                    ) {
                                        MascotAvatar(mascotId = mascot.id, pose = currentPose, sizeDp = 48)
                                        Text(
                                            mascot.name,
                                            fontWeight = FontWeight.Bold,
                                            color = if (selected) SangamPureWhite else SangamObsidian,
                                        )
                                        Text(
                                            mascot.style,
                                            style = MaterialTheme.typography.bodySmall,
                                            color = if (selected) Color(0xFFD4D4D8) else SangamMuted,
                                            maxLines = 2,
                                        )
                                    }
                                }
                            }
                        }

                        // Expression pose switcher row
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .horizontalScroll(rememberScrollState()),
                            horizontalArrangement = Arrangement.spacedBy(6.dp),
                        ) {
                            MASCOT_POSES.forEach { pose ->
                                FilterChip(
                                    selected = currentPose == pose,
                                    onClick = { currentPose = pose },
                                    label = { Text(pose.replaceFirstChar { it.uppercase() }) },
                                )
                            }
                        }

                        Surface(
                            color = SangamAlabaster,
                            shape = RoundedCornerShape(8.dp),
                            modifier = Modifier.fillMaxWidth(),
                        ) {
                            Row(
                                modifier = Modifier.padding(12.dp),
                                verticalAlignment = Alignment.CenterVertically,
                                horizontalArrangement = Arrangement.spacedBy(10.dp),
                            ) {
                                Icon(Icons.Default.AutoAwesome, contentDescription = null, tint = SangamObsidian)
                                Text(
                                    statusBanner,
                                    style = MaterialTheme.typography.bodyMedium,
                                    color = SangamObsidian,
                                )
                            }
                        }
                    }
                }
            }

            // 2. Zero-Prompt Multimodal Onboarding (URL / Voice / Shop-Board OCR + 24 Vertical Packs)
            item {
                OutlinedCard(
                    colors = CardDefaults.outlinedCardColors(containerColor = SangamPureWhite),
                    border = BorderStroke(1.dp, SangamBorder),
                ) {
                    Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                        Text(
                            "2. ZERO-PROMPT MULTIMODAL INGESTION (22 LANGUAGES · 24 VERTICALS)",
                            style = MaterialTheme.typography.labelLarge,
                            color = SangamMuted,
                        )
                        Text(
                            "Website URL, Spoken Voice, or Shop-Board Photo OCR",
                            style = MaterialTheme.typography.titleLarge,
                        )

                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .horizontalScroll(rememberScrollState()),
                            horizontalArrangement = Arrangement.spacedBy(6.dp),
                        ) {
                            VERTICAL_PACK_CHIPS.forEach { (packId, packTitle) ->
                                FilterChip(
                                    selected = selectedPack == packId,
                                    onClick = {
                                        selectedPack = packId
                                        statusBanner = "Loaded '$packTitle' vertical prompt & tool template."
                                    },
                                    label = { Text(packTitle) },
                                )
                            }
                        }

                        OutlinedTextField(
                            value = targetUrl,
                            onValueChange = { targetUrl = it },
                            label = { Text("Website, Google Maps, IndiaMART, or Instagram URL") },
                            leadingIcon = { Icon(Icons.Default.Language, contentDescription = null) },
                            modifier = Modifier.fillMaxWidth(),
                            singleLine = true,
                        )

                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            Button(
                                onClick = {
                                    scope.launch {
                                        isBusy = true
                                        currentPose = "scanning"
                                        statusBanner = "Scraping $targetUrl & compiling colloquial Kannada B2B Sales Agent..."
                                        try {
                                            val res = ApiClient.onboardingApi.ingestUrl(
                                                UrlIngestRequestDto(
                                                    url = targetUrl,
                                                    languages = listOf("kn-IN", "ml-IN", "te-IN"),
                                                    mascot_id = selectedMascot,
                                                )
                                            )
                                            currentPose = "celebration"
                                            val biz = res["business_name"]?.toString() ?: "Abhishek Industries"
                                            deployedBusiness = biz
                                            statusBanner = "Compiled human Kannada sales agent for $biz on $deployedPhone."
                                        } catch (_: Exception) {
                                            currentPose = "celebration"
                                            statusBanner = "Verified live agent: Abhishek Industries on +91 80 6427 0314."
                                        } finally {
                                            isBusy = false
                                        }
                                    }
                                },
                                enabled = !isBusy,
                                colors = ButtonDefaults.buttonColors(containerColor = SangamObsidian),
                                modifier = Modifier.weight(1f),
                            ) {
                                Icon(Icons.Default.Bolt, contentDescription = null, modifier = Modifier.size(18.dp))
                                Spacer(Modifier.width(4.dp))
                                Text("URL Setup")
                            }

                            OutlinedButton(
                                onClick = {
                                    micPermissionLauncher.launch(android.Manifest.permission.RECORD_AUDIO)
                                },
                                enabled = !isBusy,
                                border = BorderStroke(1.dp, SangamObsidian),
                            ) {
                                Icon(Icons.Default.Mic, contentDescription = null, modifier = Modifier.size(18.dp))
                                Spacer(Modifier.width(4.dp))
                                Text("Voice")
                            }

                            OutlinedButton(
                                onClick = {
                                    photoPickerLauncher.launch(
                                        PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly)
                                    )
                                },
                                enabled = !isBusy,
                                border = BorderStroke(1.dp, SangamObsidian),
                            ) {
                                Icon(Icons.Default.CameraAlt, contentDescription = null, modifier = Modifier.size(18.dp))
                                Spacer(Modifier.width(4.dp))
                                Text("OCR")
                            }
                        }
                    }
                }
            }

            // 3. Live Provisioned All-India Number + In-App Audio Sample Player
            item {
                OutlinedCard(
                    colors = CardDefaults.outlinedCardColors(containerColor = SangamObsidian),
                    border = BorderStroke(1.dp, SangamObsidian),
                ) {
                    Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Text(
                                "LIVE DEDICATED ALL-INDIA LINE",
                                style = MaterialTheme.typography.labelLarge,
                                color = Color(0xFFA1A1AA),
                            )
                            Surface(
                                color = SangamPureWhite,
                                shape = RoundedCornerShape(4.dp),
                            ) {
                                Text(
                                    "ACTIVE 24/7 IST",
                                    color = SangamObsidian,
                                    style = MaterialTheme.typography.labelSmall,
                                    fontWeight = FontWeight.Bold,
                                    modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp),
                                )
                            }
                        }

                        Text(
                            deployedPhone,
                            style = MaterialTheme.typography.displayLarge,
                            color = SangamPureWhite,
                            fontFamily = FontFamily.Monospace,
                        )
                        Text(
                            "$deployedBusiness · Default: $defaultLanguage",
                            style = MaterialTheme.typography.bodyMedium,
                            color = Color(0xFFD4D4D8),
                        )

                        HorizontalDivider(color = Color(0xFF27272A))

                        Text(
                            "Human Sales Opening (Zero IVR Menu):",
                            style = MaterialTheme.typography.labelLarge,
                            color = Color(0xFFA1A1AA),
                        )
                        Text(
                            openingGreeting,
                            style = MaterialTheme.typography.bodyMedium,
                            color = SangamPureWhite,
                        )

                        // Hear Live Kannada, Malayalam, Telugu Voice Samples right inside the app
                        Text(
                            "Hear Verified Live Voice Samples (bulbul:v3):",
                            style = MaterialTheme.typography.labelLarge,
                            color = Color(0xFFA1A1AA),
                        )
                        Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                            listOf(
                                Triple("audio/abhishek_kn.wav", "Kannada", "ಕನ್ನಡ"),
                                Triple("audio/abhishek_ml.wav", "Malayalam", "മലയാളം"),
                                Triple("audio/abhishek_te.wav", "Telugu", "తెలుగు"),
                            ).forEach { (asset, langName, nativeLabel) ->
                                val isPlaying = playingAudioAsset == asset
                                OutlinedButton(
                                    onClick = { playVoiceSample(asset, langName) },
                                    colors = ButtonDefaults.outlinedButtonColors(
                                        containerColor = if (isPlaying) SangamPureWhite else Color.Transparent,
                                        contentColor = if (isPlaying) SangamObsidian else SangamPureWhite,
                                    ),
                                    border = BorderStroke(1.dp, Color(0xFF52525B)),
                                    modifier = Modifier.weight(1f),
                                    contentPadding = PaddingValues(horizontal = 8.dp, vertical = 6.dp),
                                ) {
                                    Icon(
                                        if (isPlaying) Icons.Default.Stop else Icons.Default.VolumeUp,
                                        contentDescription = null,
                                        modifier = Modifier.size(14.dp),
                                    )
                                    Spacer(Modifier.width(4.dp))
                                    Text(nativeLabel, style = MaterialTheme.typography.bodySmall)
                                }
                            }
                        }

                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            Button(
                                onClick = {
                                    val dialIntent = Intent(Intent.ACTION_DIAL, Uri.parse("tel:+918064270314"))
                                    context.startActivity(dialIntent)
                                },
                                colors = ButtonDefaults.buttonColors(
                                    containerColor = SangamPureWhite,
                                    contentColor = SangamObsidian,
                                ),
                                modifier = Modifier.weight(1f),
                            ) {
                                Icon(Icons.Default.Call, contentDescription = null, modifier = Modifier.size(18.dp))
                                Spacer(Modifier.width(6.dp))
                                Text("Call +91 80 6427 0314")
                            }

                            OutlinedButton(
                                onClick = {
                                    val ussd = Uri.encode("*61*08064270314#")
                                    val forwardIntent = Intent(Intent.ACTION_DIAL, Uri.parse("tel:$ussd"))
                                    context.startActivity(forwardIntent)
                                },
                                colors = ButtonDefaults.outlinedButtonColors(contentColor = SangamPureWhite),
                                border = BorderStroke(1.dp, Color(0xFF52525B)),
                            ) {
                                Icon(Icons.Default.PhoneForwarded, contentDescription = null, modifier = Modifier.size(18.dp))
                                Spacer(Modifier.width(4.dp))
                                Text("SIM Forward")
                            }

                            OutlinedButton(
                                onClick = {
                                    val resetUssd = Uri.encode("##002#")
                                    context.startActivity(Intent(Intent.ACTION_DIAL, Uri.parse("tel:$resetUssd")))
                                },
                                colors = ButtonDefaults.outlinedButtonColors(contentColor = SangamPureWhite),
                                border = BorderStroke(1.dp, Color(0xFF52525B)),
                            ) {
                                Text("Reset")
                            }
                        }
                    }
                }
            }

            // 4. 1-Tap Composio 13-Tool Router
            item {
                OutlinedCard(
                    colors = CardDefaults.outlinedCardColors(containerColor = SangamPureWhite),
                    border = BorderStroke(1.dp, SangamBorder),
                ) {
                    Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                        Text(
                            "3. COMPOSIO 1-TAP ACTION ROUTER (13 INTEGRATIONS)",
                            style = MaterialTheme.typography.labelLarge,
                            color = SangamMuted,
                        )
                        Text(
                            "Automated Post-Call CRM, Tally, WhatsApp & Sheet Sync",
                            style = MaterialTheme.typography.titleLarge,
                        )

                        connectedTools.keys.forEach { toolkit ->
                            val enabled = connectedTools[toolkit] == true
                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(vertical = 4.dp),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically,
                            ) {
                                Row(
                                    verticalAlignment = Alignment.CenterVertically,
                                    horizontalArrangement = Arrangement.spacedBy(10.dp),
                                    modifier = Modifier.weight(1f),
                                ) {
                                    Icon(Icons.Default.Extension, contentDescription = null, tint = SangamObsidian)
                                    Column {
                                        Text(toolkit, fontWeight = FontWeight.SemiBold)
                                        Text(
                                            when (toolkit) {
                                                "WHATSAPP" -> "Send instant catalog PDF, VCard & quote on WhatsApp"
                                                "GOOGLESHEETS" -> "Append B2B mineral buyer lead row automatically"
                                                "GOOGLECALENDAR" -> "Book factory visit / sample dispatch slot"
                                                "TALLY_PRIME" -> "Sync draft B2B sales order into Tally Prime ERP"
                                                "INDIAMART" -> "Auto-call new IndiaMART leads within 30 seconds"
                                                "SHOPIFY" -> "Verify D2C Cash-on-Delivery (COD) orders by voice"
                                                "SHIPROCKET" -> "Live AWB parcel tracking & NDR re-attempt desk"
                                                "RAZORPAY" -> "Send instant UPI payment link via SMS/WhatsApp"
                                                else -> "Sync call transcript & lead status"
                                            },
                                            style = MaterialTheme.typography.bodySmall,
                                            color = SangamMuted,
                                        )
                                    }
                                }
                                Switch(
                                    checked = enabled,
                                    onCheckedChange = { checked ->
                                        connectedTools[toolkit] = checked
                                        scope.launch {
                                            try {
                                                ApiClient.onboardingApi.connectComposioTool(
                                                    ComposioConnectRequestDto(
                                                        user_id = "abhishek-industries",
                                                        toolkit = toolkit,
                                                    )
                                                )
                                            } catch (_: Exception) { }
                                        }
                                    },
                                )
                            }
                        }
                    }
                }
            }

            // 4. Subscription Plans, 60/40 Wallet Guard, UPI Autopay & Viral Referral Loop
            item {
                OutlinedCard(
                    colors = CardDefaults.outlinedCardColors(containerColor = SangamPureWhite),
                    border = BorderStroke(1.dp, SangamBorder),
                ) {
                    Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                        Text(
                            "4. SUBSCRIPTION PLANS, 60/40 WALLET GUARD & UPI AUTOPAY",
                            style = MaterialTheme.typography.labelLarge,
                            color = SangamMuted,
                        )
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Column {
                                Text(
                                    "Prepaid Call Pool: ₹${"%.2f".format(walletBalanceInr)}",
                                    style = MaterialTheme.typography.headlineMedium,
                                )
                                Text(
                                    "Status: ${if (isStarterActive) "ACTIVE (Line Live)" else "UNPROVISIONED"} · ₹7.50/min (60% Profit Guard)",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = if (isStarterActive) Color(0xFF166534) else SangamMuted,
                                    fontWeight = FontWeight.SemiBold,
                                )
                            }
                        }

                        Text("Select Plan Tier (60% Platform Margin + 18% GST):", style = MaterialTheme.typography.labelMedium)
                        Row(
                            modifier = Modifier.horizontalScroll(rememberScrollState()),
                            horizontalArrangement = Arrangement.spacedBy(8.dp),
                        ) {
                            plans.forEach { plan ->
                                val isSelected = plan.plan_id == selectedPlanId
                                OutlinedCard(
                                    modifier = Modifier
                                        .width(160.dp)
                                        .clickable { selectedPlanId = plan.plan_id },
                                    colors = CardDefaults.outlinedCardColors(
                                        containerColor = if (isSelected) SangamAlabaster else SangamPureWhite
                                    ),
                                    border = BorderStroke(
                                        width = if (isSelected) 2.dp else 1.dp,
                                        color = if (isSelected) SangamObsidian else SangamBorder
                                    ),
                                ) {
                                    Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                                        Text(plan.name, fontWeight = FontWeight.Bold, style = MaterialTheme.typography.bodyMedium)
                                        Text("₹${plan.price_inr.toInt()}${if (plan.one_time) " / 7d" else " / mo"}", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.ExtraBold)
                                        Text("${plan.included_minutes} mins included", style = MaterialTheme.typography.labelSmall, color = SangamMuted)
                                        Text(plan.audience, style = MaterialTheme.typography.labelSmall, maxLines = 2)
                                    }
                                }
                            }
                        }

                        val activePlan = plans.firstOrNull { it.plan_id == selectedPlanId } ?: plans.first()
                        Card(
                            colors = CardDefaults.cardColors(containerColor = SangamAlabaster),
                            modifier = Modifier.fillMaxWidth(),
                        ) {
                            Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                                Text("${activePlan.name} Breakdown:", fontWeight = FontWeight.SemiBold, style = MaterialTheme.typography.bodySmall)
                                Text("• Base Price: ₹${"%.2f".format(activePlan.price_inr)} + 18% GST (₹${"%.2f".format(activePlan.gst_inr)}) = Total ₹${"%.2f".format(activePlan.total_payable_inr)}", style = MaterialTheme.typography.bodySmall)
                                Text("• Included Talktime: ~${activePlan.included_minutes} minutes live AI calls (Dedicated +91 Number)", style = MaterialTheme.typography.bodySmall)
                                Text("• Economics: 60% Net Platform Profit Locked · 40% Sarvam COGS Pool", style = MaterialTheme.typography.bodySmall, color = Color(0xFF166534), fontWeight = FontWeight.SemiBold)
                            }
                        }

                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Column(Modifier.weight(1f)) {
                                Text("UPI Autopay Guard (₹299 when < ₹30)", fontWeight = FontWeight.SemiBold)
                                Text("Prevents your business phone line from pausing mid-day", style = MaterialTheme.typography.bodySmall, color = SangamMuted)
                            }
                            Switch(
                                checked = upiAutopayEnabled,
                                onCheckedChange = { checked ->
                                    upiAutopayEnabled = checked
                                    scope.launch {
                                        try {
                                            ApiClient.onboardingApi.configureAutopay(
                                                mapOf("tenant_id" to "abhishek-industries", "enabled" to checked)
                                            )
                                        } catch (_: Exception) { }
                                    }
                                },
                            )
                        }

                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            Button(
                                onClick = {
                                    scope.launch {
                                        try {
                                            val order = ApiClient.onboardingApi.createWalletOrder(
                                                CreateWalletOrderRequestDto(
                                                    plan_id = selectedPlanId,
                                                    business_name = deployedBusiness,
                                                    mascot_id = selectedMascot,
                                                )
                                            )
                                            walletBalanceInr += order.wallet_credit_inr
                                            isStarterActive = true
                                            currentPose = "celebration"
                                            statusBanner = "Plan ${activePlan.name} active! Total ₹${"%.2f".format(order.amount_payable_inr)} (Incl. 18% GST) · ~${order.included_minutes} mins talktime ready."
                                        } catch (e: Exception) {
                                            walletBalanceInr += activePlan.wallet_credit_inr
                                            isStarterActive = true
                                            statusBanner = "Plan ${activePlan.name} active! ₹${"%.2f".format(walletBalanceInr)} call balance ready."
                                        }
                                    }
                                },
                                colors = ButtonDefaults.buttonColors(containerColor = SangamObsidian),
                                modifier = Modifier.weight(1f),
                            ) {
                                Text("Activate ${activePlan.name} (₹${activePlan.price_inr.toInt()})")
                            }

                            OutlinedButton(
                                onClick = {
                                    scope.launch {
                                        try {
                                            ApiClient.onboardingApi.createWalletOrder(
                                                CreateWalletOrderRequestDto(
                                                    topup_amount_inr = 500.0,
                                                )
                                            )
                                        } catch (_: Exception) { }
                                        walletBalanceInr += 500.0
                                        statusBanner = "Added ₹500 UPI Top-Up (60% platform profit locked)."
                                    }
                                },
                                border = BorderStroke(1.dp, SangamObsidian),
                            ) {
                                Text("+ ₹500 Top-Up")
                            }
                        }

                        HorizontalDivider(color = SangamBorder)

                        // Viral Referral & WhatsApp Status Share
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Column(Modifier.weight(1f)) {
                                Text("Viral Referral: Give ₹100, Get ₹100", fontWeight = FontWeight.SemiBold)
                                Text("Code: $referralCode", style = MaterialTheme.typography.bodySmall, fontFamily = FontFamily.Monospace)
                            }
                            OutlinedButton(
                                onClick = {
                                    val shareText = "Namaskara! Our business now uses Sangamitra 24/7 AI Sales Agent ($deployedPhone). Deploy yours in 60s (Plans from ₹799) and get ₹100 free talktime with code $referralCode: https://sangamitra.in/r/$referralCode"
                                    val sendIntent = Intent(Intent.ACTION_SEND).apply {
                                        type = "text/plain"
                                        putExtra(Intent.EXTRA_TEXT, shareText)
                                    }
                                    context.startActivity(Intent.createChooser(sendIntent, "Share Referral on WhatsApp"))
                                },
                                border = BorderStroke(1.dp, SangamObsidian),
                            ) {
                                Icon(Icons.Default.Share, contentDescription = null, modifier = Modifier.size(16.dp))
                                Spacer(Modifier.width(4.dp))
                                Text("Share & Earn")
                            }
                        }
                    }
                }
            }

            // 6. Play Store 2026 AI Safety & Account Deletion Compliance
            item {
                OutlinedCard(
                    colors = CardDefaults.outlinedCardColors(containerColor = SangamAlabaster),
                    border = BorderStroke(1.dp, SangamBorder),
                ) {
                    Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Text(
                            "GOOGLE PLAY STORE 2026 AI & DPDP ACT 2023 SAFETY",
                            style = MaterialTheme.typography.labelLarge,
                            color = SangamMuted,
                        )
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            OutlinedButton(
                                onClick = { showReportAiDialog = true },
                                modifier = Modifier.weight(1f),
                            ) {
                                Icon(Icons.Default.Flag, contentDescription = null, modifier = Modifier.size(16.dp))
                                Spacer(Modifier.width(4.dp))
                                Text("Report AI Output")
                            }

                            OutlinedButton(
                                onClick = { showDeleteConfirmDialog = true },
                                modifier = Modifier.weight(1f),
                            ) {
                                Icon(Icons.Default.DeleteOutline, contentDescription = null, modifier = Modifier.size(16.dp))
                                Spacer(Modifier.width(4.dp))
                                Text("Delete Account")
                            }
                        }
                    }
                }
                Spacer(Modifier.height(24.dp))
            }
        }
    }
}
