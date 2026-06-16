package com.chettyok.macroreel;

import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.os.Parcelable;
import com.getcapacitor.BridgeActivity;
import java.util.ArrayList;

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
        if (Intent.ACTION_SEND.equals(action) || Intent.ACTION_SEND_MULTIPLE.equals(action)) {
            sharedText = firstNonEmpty(
                intent.getStringExtra(Intent.EXTRA_TEXT),
                intent.getStringExtra(Intent.EXTRA_SUBJECT),
                streamUri(intent)
            );
        } else if (Intent.ACTION_VIEW.equals(action) && intent.getData() != null) {
            sharedText = intent.getDataString();
        }

        String importUrl = "https://localhost/import";
        if (sharedText != null && !sharedText.trim().isEmpty()) {
            importUrl += "?url=" + Uri.encode(sharedText.trim());
        }
        getBridge().getWebView().post(() -> getBridge().getWebView().loadUrl(importUrl));
    }

    private String firstNonEmpty(String... values) {
        for (String value : values) {
            if (value != null && !value.trim().isEmpty()) {
                return value;
            }
        }
        return null;
    }

    private String streamUri(Intent intent) {
        Parcelable stream = intent.getParcelableExtra(Intent.EXTRA_STREAM);
        if (stream instanceof Uri) {
            return stream.toString();
        }
        ArrayList<Uri> streams = intent.getParcelableArrayListExtra(Intent.EXTRA_STREAM);
        if (streams != null && !streams.isEmpty() && streams.get(0) != null) {
            return streams.get(0).toString();
        }
        return null;
    }
}
