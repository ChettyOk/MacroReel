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
        if (intent == null) {
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
            Uri data = intent.getData();
            if ("macroreel".equals(data.getScheme()) && "import".equals(data.getHost())) {
                String urlParam = data.getQueryParameter("url");
                if (urlParam != null && !urlParam.trim().isEmpty()) {
                    dispatchImportDeepLink(Uri.encode(urlParam.trim()));
                } else {
                    scheduleImportNavigation("https://localhost/import");
                }
                dispatchUrlOpenToBridge(intent);
                return;
            }
            sharedText = intent.getDataString();
        }

        if (sharedText == null || sharedText.trim().isEmpty()) {
            return;
        }

        String encoded = Uri.encode(sharedText.trim());
        dispatchImportDeepLink(encoded);
    }

    private void dispatchImportDeepLink(String encodedUrlParam) {
        String importUrl = "https://localhost/import?url=" + encodedUrlParam;
        Uri deepLink = Uri.parse("macroreel://import?url=" + encodedUrlParam);

        Intent viewIntent = new Intent(Intent.ACTION_VIEW, deepLink);
        setIntent(viewIntent);
        dispatchUrlOpenToBridge(viewIntent);
        scheduleImportNavigation(importUrl);
    }

    private void dispatchUrlOpenToBridge(Intent intent) {
        Runnable dispatch = new Runnable() {
            private int attempts = 0;

            @Override
            public void run() {
                if (getBridge() != null) {
                    getBridge().onNewIntent(intent);
                    return;
                }
                if (attempts++ < 80) {
                    getWindow().getDecorView().postDelayed(this, 75);
                }
            }
        };
        getWindow().getDecorView().post(dispatch);
    }

    private void scheduleImportNavigation(String importUrl) {
        Runnable load = new Runnable() {
            private int attempts = 0;

            @Override
            public void run() {
                if (getBridge() != null && getBridge().getWebView() != null) {
                    getBridge().getWebView().loadUrl(importUrl);
                    return;
                }
                if (attempts++ < 80) {
                    getWindow().getDecorView().postDelayed(this, 75);
                }
            }
        };
        getWindow().getDecorView().post(load);
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
