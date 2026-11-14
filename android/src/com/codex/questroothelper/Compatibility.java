package com.codex.questroothelper;
import android.os.Build;
final class Compatibility {
  static boolean supported() {
    return "seacliff".equals(Build.DEVICE) && "51503870035800340".equals(Build.VERSION.INCREMENTAL);
  }
}
