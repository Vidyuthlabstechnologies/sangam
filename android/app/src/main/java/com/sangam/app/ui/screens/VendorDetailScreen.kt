package com.sangam.app.ui.screens

import com.sangam.app.R
import com.sangam.app.ui.components.str

import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.heading
import com.sangam.app.ui.components.friendlyError
import com.sangam.app.ui.components.humanize
import com.sangam.app.ui.components.StatusLabel
import com.sangam.app.ui.components.ErrorState
import com.sangam.app.ui.components.PrimaryButton
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Verified
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.sangam.app.network.ApiClient
import com.sangam.app.network.VendorDto
import com.sangam.app.network.VendorLicenceDto
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun VendorDetailScreen(
    vendorId: String,
    onBack: () -> Unit,
    onQualificationSubmitted: (String) -> Unit,
) {
    var vendor by remember { mutableStateOf<VendorDto?>(null) }
    var loading by remember { mutableStateOf(true) }
    var busy by remember { mutableStateOf(false) }
    var message by remember { mutableStateOf<String?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()

    LaunchedEffect(vendorId) {
        try {
            vendor = ApiClient.api.getVendor(vendorId)
        } catch (e: Exception) {
            error = e.message ?: str(R.string.could_not_load_vendor)
        }
        loading = false
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(vendor?.name ?: str(R.string.vendor)) },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = str(R.string.back))
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.surface
                ),
            )
        }
    ) { padding ->
        if (loading) {
            Box(Modifier.fillMaxSize().padding(padding), contentAlignment = Alignment.Center) {
                CircularProgressIndicator()
            }
            return@Scaffold
        }

        val v = vendor
        if (v == null) {
            Box(Modifier.fillMaxSize().padding(padding).padding(24.dp), contentAlignment = Alignment.Center) {
                ErrorState(error ?: str(R.string.this_vendor_could_not_be_found), onRetry = null)
            }
            return@Scaffold
        }

        Column(
            Modifier
                .fillMaxSize()
                .padding(padding)
                .verticalScroll(rememberScrollState())
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Card(
        Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        border = CardDefaults.outlinedCardBorder(),
    ) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text(v.legal_name ?: v.name, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                    v.gstin?.let { Text(str(R.string.gstin, it), style = MaterialTheme.typography.bodyMedium) }
                    v.address?.let {
                        Text(
                            it,
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    Spacer(Modifier.height(4.dp))
                    StatusLabel(humanize(v.status))
                }
            }

            Text(
                str(R.string.regulatory_licences),
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
                modifier = Modifier.padding(top = 4.dp).semantics { heading() },
            )

            if (v.licences.isEmpty()) {
                Text(
                    str(R.string.no_licences_on_file),
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            } else {
                v.licences.forEach { LicenceCard(it) }
            }

            message?.let {
                Surface(color = MaterialTheme.colorScheme.primaryContainer, shape = MaterialTheme.shapes.small) {
                    Text(
                        it,
                        modifier = Modifier.padding(12.dp),
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onPrimaryContainer,
                    )
                }
            }
            error?.let { Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodyMedium) }

            if (v.status != "pending_qualification" && v.licences.isNotEmpty()) {
                PrimaryButton(
                    onClick = {
                        scope.launch {
                            busy = true; error = null
                            try {
                                val res = ApiClient.api.submitForQualification(vendorId)
                                message = res.message
                                vendor = ApiClient.api.getVendor(vendorId)
                                onQualificationSubmitted(res.workflow_id)
                            } catch (e: Exception) {
                                error = friendlyError(e, str(R.string.submit_for_qualification))
                            }
                            busy = false
                        }
                    },
                    enabled = !busy,
                    modifier = Modifier.fillMaxWidth(),
                ) { Text(str(R.string.submit_for_qualification_2)) }
            }
        }
    }
}

@Composable
private fun LicenceCard(licence: VendorLicenceDto) {
    Card(
        Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        border = CardDefaults.outlinedCardBorder(),
    ) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    licence.licence_type.uppercase(),
                    style = MaterialTheme.typography.labelLarge,
                    fontWeight = FontWeight.Bold,
                )
                if (licence.verified) {
                    Spacer(Modifier.width(6.dp))
                    Icon(
                        Icons.Default.Verified,
                        contentDescription = str(R.string.verified),
                        tint = MaterialTheme.colorScheme.primary,
                        modifier = Modifier.size(16.dp),
                    )
                }
            }
            Text(licence.licence_number, style = MaterialTheme.typography.bodyLarge, fontWeight = FontWeight.Medium)
            licence.issuing_authority?.let {
                Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }

            val days = licence.days_until_expiry
            val expiryText = when {
                licence.is_expired -> "EXPIRED"
                days != null -> str(R.string.valid_until_days, licence.expiry_date, days)
                else -> str(R.string.expiry_unknown)
            }
            Text(
                expiryText,
                style = MaterialTheme.typography.bodySmall,
                color = when {
                    licence.is_expired -> MaterialTheme.colorScheme.error
                    days != null && days <= 90 -> MaterialTheme.colorScheme.tertiary
                    else -> MaterialTheme.colorScheme.onSurfaceVariant
                },
                fontWeight = if (licence.is_expired || (days != null && days <= 90)) FontWeight.Medium else FontWeight.Normal,
            )

            licence.extraction_confidence?.let {
                Text(
                    if (it >= 0.9) str(R.string.read_from_photo_high_confidence) else str(R.string.read_from_photo_check_the_details),
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}
