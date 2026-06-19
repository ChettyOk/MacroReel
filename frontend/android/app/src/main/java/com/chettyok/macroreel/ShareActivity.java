package com.chettyok.macroreel;

import android.app.Activity;
import android.content.ClipData;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.os.Parcelable;
import java.util.ArrayList;

/**
 * Dedicated share target so MacroReel appears in TikTok/Instagram share sheets.
 * Forwards shared text/URLs to MainActivity via macroreel://import deep link.
 */
public class ShareActivity extends Activity {
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        forwardShare(getIntent());
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        forwardShare(intent);
    }

    private void forwardShare(Intent intent) {
        if (intent == null) {
            finish();
            return;
        }

        String sharedText = extractSharedText(intent);
        Intent launch = new Intent(this, MainActivity.class);
        launch.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_SINGLE_TOP);
        launch.setAction(Intent.ACTION_VIEW);

        if (sharedText != null && !sharedText.trim().isEmpty()) {
            launch.setData(Uri.parse("macroreel://import?url=" + Uri.encode(sharedText.trim())));
        } else {
            launch.setData(Uri.parse("macroreel://import"));
        }

        startActivity(launch);
        finish();
    }

    private String extractSharedText(Intent intent) {
        String action = intent.getAction();
        if (Intent.ACTION_SEND.equals(action) || Intent.ACTION_SEND_MULTIPLE.equals(action)) {
            return firstNonEmpty(
                intent.getStringExtra(Intent.EXTRA_TEXT),
                intent.getStringExtra(Intent.EXTRA_SUBJECT),
                clipDataText(intent),
                streamUri(intent)
            );
        }
        if (Intent.ACTION_VIEW.equals(action) && intent.getData() != null) {
            return intent.getDataString();
        }
        return null;
    }

    private String clipDataText(Intent intent) {
        ClipData clip = intent.getClipData();
        if (clip == null) {
            return null;
        }
        for (int i = 0; i < clip.getItemCount(); i++) {
            ClipData.Item item = clip.getItemAt(i);
            if (item.getText() != null && item.getText().length() > 0) {
                return item.getText().toString();
            }
            if (item.getUri() != null) {
                return item.getUri().toString();
            }
        }
        return null;
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
