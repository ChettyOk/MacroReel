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
        if (intent == null) {
            return;
        }

        Uri data = intent.getData();
        if (Intent.ACTION_VIEW.equals(intent.getAction()) && data != null && "macroreel".equals(data.getScheme()) && "import".equals(data.getHost())) {
            String urlParam = data.getQueryParameter("url");
            String importUrl = "https://localhost/import";
            if (urlParam != null && !urlParam.trim().isEmpty()) {
                importUrl += "?url=" + Uri.encode(urlParam.trim());
            }
            dispatchUrlOpenToBridge(intent);
            scheduleImportNavigation(importUrl);
        }
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
}
