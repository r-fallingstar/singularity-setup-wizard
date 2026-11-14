package com.codex.questroothelper;
import android.content.Context;
import java.util.Locale;
final class Words {
  static boolean ja(Context c) { return c.getSharedPreferences("wizard",0).getString("language",Locale.getDefault().getLanguage()).equals("ja"); }
  static String text(Context c,String ja,String en) { return ja(c)?ja:en; }
}
