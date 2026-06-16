package com.chettyok.macroreel;

import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        handleIncomingIntent(getIntent());
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        handleIncomingIntent(intent);
    }

    private void handleIncomingIntent(Intent intent) {
        if (intent == null || getBridge() == null || getBridge().getWebView() == null) {
            return;
        }

        String sharedText = null;
        String action = intent.getAction();
        if (Intent.ACTION_SEND.equals(action)) {
            sharedText = intent.getStringExtra(Intent.EXTRA_TEXT);
        } else if (Intent.ACTION_VIEW.equals(action) && intent.getData() != null) {
            sharedText = intent.getDataString();
        }

        if (sharedText == null || sharedText.trim().isEmpty()) {
            return;
        }

        String importUrl = "https://localhost/import?url=" + Uri.encode(sharedText.trim());
        getBridge().getWebView().post(() -> getBridge().getWebView().loadUrl(importUrl));
    }
}
