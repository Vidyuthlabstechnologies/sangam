package com.sangam.app.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Description
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.sangam.app.network.ApiClient
import com.sangam.app.network.CreateVendorRequest
import com.sangam.app.network.ExtractedDocumentDto
import kotlinx.coroutines.launch
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.toRequestBody

/**
 * Two-stage vendor creation: register the supplier, then attach their
 * regulatory licence for automatic extraction.
 *
 * The extraction result is shown before it is trusted. Fields the model was
 * unsure about are called out, because a mis-read expiry date means shipping
 * against a lapsed licence.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AddVendorScreen(
    onDone: (String) -> Unit,
    onBack: () -> Unit,
    sampleLicenceBytes: () -> ByteArray,
) {
    var name by remember { mutableStateOf("Meridian Life Sciences") }
    var gstin by remember { mutableStateOf("29AABCM1234K1Z5") }
    var email by remember { mutableStateOf("qa@meridian.example") }

    var vendorId by remember { mutableStateOf<String?>(null) }
    var busy by remember { mutableStateOf(false) }
    var statusText by remember { mutableStateOf<String?>(null) }
    var extracted by remember { mutableStateOf<ExtractedDocumentDto?>(null) }
    var error by remember { mutableStateOf<String?>(null) }

    val scope = rememberCoroutineScope()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Add vendor") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.surface
                ),
            )
        }
    ) { padding ->
        Column(
            Modifier
                .fillMaxSize()
                .padding(padding)
                .verticalScroll(rememberScrollState())
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            OutlinedTextField(
                value = name,
                onValueChange = { name = it },
                label = { Text("Vendor name") },
                singleLine = true,
                enabled = vendorId == null,
                modifier = Modifier.fillMaxWidth(),
            )
            OutlinedTextField(
                value = gstin,
                onValueChange = { gstin = it },
                label = { Text("GSTIN") },
                singleLine = true,
                enabled = vendorId == null,
                modifier = Modifier.fillMaxWidth(),
            )
            OutlinedTextField(
                value = email,
                onValueChange = { email = it },
                label = { Text("Contact email") },
                singleLine = true,
                enabled = vendorId == null,
                modifier = Modifier.fillMaxWidth(),
            )

            if (vendorId == null) {
                Button(
                    onClick = {
                        scope.launch {
                            busy = true; error = null
                            try {
                                val v = ApiClient.api.createVendor(
                                    CreateVendorRequest(
                                        name = name,
                                        gstin = gstin.ifBlank { null },
                                        contact_email = email.ifBlank { null },
                                    )
                                )
                                vendorId = v.id
                                statusText = "Vendor registered. Now attach their licence."
                            } catch (e: Exception) {
                                error = e.message ?: "Could not create vendor"
                            }
                            busy = false
                        }
                    },
                    enabled = !busy && name.isNotBlank(),
                    modifier = Modifier.fillMaxWidth(),
                ) { Text("Register vendor") }
            } else {
                Button(
                    onClick = {
                        scope.launch {
                            busy = true; error = null
                            statusText = "Extracting licence with Sarvam…"
                            try {
                                val bytes = sampleLicenceBytes()
                                val part = MultipartBody.Part.createFormData(
                                    "file", "cdsco_licence.pdf",
                                    bytes.toRequestBody("application/pdf".toMediaTypeOrNull()),
                                )
                                val typePart = "licence"
                                    .toRequestBody("text/plain".toMediaTypeOrNull())
                                extracted = ApiClient.api.uploadVendorDocument(
                                    vendorId!!, part, typePart
                                )
                                statusText = null
                            } catch (e: Exception) {
                                error = e.message ?: "Extraction failed"
                                statusText = null
                            }
                            busy = false
                        }
                    },
                    enabled = !busy,
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Icon(Icons.Default.Description, contentDescription = null)
                    Spacer(Modifier.width(8.dp))
                    Text("Capture CDSCO licence")
                }
            }

            if (busy) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    CircularProgressIndicator(Modifier.size(18.dp), strokeWidth = 2.dp)
                    Spacer(Modifier.width(10.dp))
                    Text(statusText ?: "Working…", style = MaterialTheme.typography.bodyMedium)
                }
            } else if (statusText != null) {
                Text(statusText!!, style = MaterialTheme.typography.bodyMedium)
            }

            error?.let {
                Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodyMedium)
            }

            extracted?.let { doc -> ExtractionResultCard(doc) }

            extracted?.let { doc ->
                val vid = vendorId
                if (vid != null) {
                    Button(
                        onClick = {
                            scope.launch {
                                busy = true
                                try {
                                    if (doc.needs_review) {
                                        ApiClient.api.confirmDocument(vid, doc.id)
                                    }
                                    onDone(vid)
                                } catch (e: Exception) {
                                    error = e.message ?: "Could not confirm"
                                }
                                busy = false
                            }
                        },
                        enabled = !busy,
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Text(if (doc.needs_review) "Confirm and continue" else "Continue")
                    }
                }
            }
        }
    }
}

@Composable
private fun ExtractionResultCard(doc: ExtractedDocumentDto) {
    val data = doc.structured_data
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(
                    Icons.Default.CheckCircle,
                    contentDescription = null,
                    tint = if (doc.needs_review) MaterialTheme.colorScheme.tertiary
                    else MaterialTheme.colorScheme.primary,
                    modifier = Modifier.size(20.dp),
                )
                Spacer(Modifier.width(8.dp))
                Text(
                    "Extracted by Sarvam",
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.SemiBold,
                )
            }

            if (data != null) {
                ExtractedRow("Licence no.", data["licence_number"]?.toString())
                ExtractedRow("Vendor", data["vendor_name"]?.toString())
                ExtractedRow("Authority", data["issuing_authority"]?.toString())
                ExtractedRow("Valid until", data["expiry_date"]?.toString())
            }

            doc.min_confidence?.let {
                Text(
                    "Lowest field confidence: ${"%.2f".format(it)}",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }

            if (doc.needs_review) {
                Surface(
                    color = MaterialTheme.colorScheme.tertiaryContainer,
                    shape = MaterialTheme.shapes.small,
                ) {
                    Text(
                        "Some fields were read with low confidence. Check them before confirming.",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onTertiaryContainer,
                        modifier = Modifier.padding(10.dp),
                    )
                }
            }

            doc.error_message?.let {
                Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
            }
        }
    }
}

@Composable
private fun ExtractedRow(label: String, value: String?) {
    if (value.isNullOrBlank() || value == "null") return
    Row(Modifier.fillMaxWidth()) {
        Text(
            label,
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.width(96.dp),
        )
        Text(value, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Medium)
    }
}
