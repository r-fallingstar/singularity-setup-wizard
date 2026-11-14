package com.codex.questroothelper;
import android.app.*;
import android.content.*;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.os.*;
import android.view.*;
import android.widget.*;
import java.io.*;
import java.util.concurrent.TimeUnit;

/** Companion wizard. Firmware setup stays explicit in the PC application. */
public class MainActivity extends Activity {
  private int page=0;
  private LinearLayout content;
  private TextView status;
  private final Handler handler=new Handler();
  private String t(String ja,String en) { return Words.text(this,ja,en); }
  @Override public void onCreate(Bundle state) {
    super.onCreate(state);
    if(state!=null)page=state.getInt("page",0);
    if(getSharedPreferences("wizard",0).getBoolean("auto_root",true))startForegroundService(new Intent(this,RootService.class));
    if(getSharedPreferences("power_settings",0).getBoolean("manual_sleep_only",false))startForegroundService(new Intent(this,AwakeService.class));
    draw();
  }
  @Override protected void onSaveInstanceState(Bundle b){super.onSaveInstanceState(b);b.putInt("page",page);}
  private TextView text(String value,int size) {
    TextView view=new TextView(this);view.setText(value);view.setTextSize(size);view.setTextColor(Color.rgb(25,44,56));
    view.setPadding(0,12,0,18);content.addView(view);return view;
  }
  private void button(String label,View.OnClickListener action) {
    Button b=new Button(this);b.setText(label);b.setTextSize(18);b.setAllCaps(false);b.setMinHeight(68);b.setOnClickListener(action);content.addView(b);
  }
  private void draw() {
    ScrollView scroll=new ScrollView(this);scroll.setBackgroundColor(Color.rgb(237,241,243));
    content=new LinearLayout(this);content.setOrientation(LinearLayout.VERTICAL);content.setPadding(40,24,40,36);
    scroll.addView(content);setContentView(scroll);
    text("Singularity Setup Wizard",27);
    button(t("English に切り替え","日本語に切り替え"),new View.OnClickListener(){public void onClick(View v){getSharedPreferences("wizard",0).edit().putString("language",Words.ja(MainActivity.this)?"en":"ja").apply();draw();}});
    String[] ja={"ようこそ","PCでセットアップ","起動時の補助","状態を確認","Virtual Desktopで確認"};
    String[] en={"Welcome","Set up from your PC","Startup assistance","Check status","Verify Virtual Desktop"};
    text((page+1)+" / 5   "+(Words.ja(this)?ja[page]:en[page]),23);
    if(page==0) {
      text(t("OS更新は停止、使いたいアプリの通信は維持。\n\nこれは非公式の補助アプリです。初回rootは公式Singularityで行います。root取得コードや公式APKは同梱していません。", "Block firmware updates while keeping the apps you use connected.\n\nThis is an unofficial companion. Initial root is performed in official Singularity. No exploit or official APK is bundled."),19);
      text(t("確認済み：Quest Pro / ビルド51503870035800340 / Singularity 1.0.8.5。その他の構成は未検証です。", "Validated: Quest Pro / build 51503870035800340 / Singularity 1.0.8.5. Other configurations are unvalidated."),16);
    } else if(page==1) {
      text(t("1. PC版ウィザードでUSB接続を確認\n2. 公式Singularityでワイヤレスデバッグと初回rootを設定\n3. PC版で設定内容を確認して適用\n\nOS更新の停止と任意の遠隔操作停止はPC版で行います。アプリ更新やMetaアカウント、ネットワークの一括遮断は変更しません。", "1. Check USB connection in the PC wizard\n2. Complete wireless debugging and initial root in official Singularity\n3. Review and apply your choices on PC\n\nFirmware protection and optional remote-action changes are applied from PC. App updates, Meta accounts and broad network filtering are left alone."),19);
      button(t("Singularityを開く","Open Singularity"),new View.OnClickListener(){public void onClick(View v){open("com.lumi.singularity","com.lumi.singularity.ui.activities.MainActivity");}});
    } else if(page==2) {
      text(t("公式SingularityのRoot on Bootで取得したrootの権限情報を補正します。補助アプリ自身はrootを取得せず、自動再起動やroot取得の繰り返しも行いません。", "This helper normalizes credentials after official Singularity Root on Boot obtains root. It does not perform an exploit, reboot automatically, or repeatedly retry an exploit."),19);
      final Switch auto=new Switch(this);auto.setText(t("起動時のroot補助","Root assistance on boot"));auto.setTextSize(19);auto.setPadding(0,20,0,20);
      auto.setChecked(getSharedPreferences("wizard",0).getBoolean("auto_root",true));content.addView(auto);
      auto.setOnCheckedChangeListener(new CompoundButton.OnCheckedChangeListener(){public void onCheckedChanged(CompoundButton b,boolean on){getSharedPreferences("wizard",0).edit().putBoolean("auto_root",on).apply();if(on)startForegroundService(new Intent(MainActivity.this,RootService.class));else stopService(new Intent(MainActivity.this,RootService.class));}});
      text(t("OFFにする場合は、先にSingularity側のRoot on BootもOFFにしてください。補助だけを止めると、元の権限不整合が再発する場合があります。", "Before turning this off, also turn off Root on Boot in Singularity. Disabling only the helper may bring back the original credential mismatch."),16);
      button(t("今のrootを確認・補助","Check and assist current root"),new View.OnClickListener(){public void onClick(View v){startForegroundService(new Intent(MainActivity.this,RootService.class));page=3;draw();}});
      text(t("追加の補助ツール", "Additional tools"),22);
      text(t("スリープと6GHzの設定にはPC版からの導入とrootが必要です。6GHz固定は、いま接続中の電波が6GHzの場合だけ利用できます。圏外でも5GHzへ切り替わらなくなります。", "Sleep and 6GHz tools require PC setup and root. Pinning works only while currently connected to a 6GHz access point; it prevents fallback to 5GHz out of range."),16);
      button(t("電源ボタンでのみスリープ", "Sleep with the power button only"),new View.OnClickListener(){public void onClick(View v){power(true);}});
      button(t("自動スリープを60秒に設定", "Set automatic sleep to 60 seconds"),new View.OnClickListener(){public void onClick(View v){power(false);}});
      button(t("現在の6GHz電波に固定", "Pin the current 6GHz access point"),new View.OnClickListener(){public void onClick(View v){confirmAction(t("6GHzが届かない場所では接続できなくなります。固定しますか？", "You will lose connection outside this 6GHz access point’s range. Pin now?"),"CLASSPATH=/data/local/tmp/ssw-wifi-admin.jar app_process /system/bin QuestWifiAdmin pin-current",null);}});
    } else if(page==3) {
      status=text(t("状態を確認しています…","Checking status…"),19);
      button(t("再確認","Refresh"),new View.OnClickListener(){public void onClick(View v){diagnose();}});diagnose();
    } else {
      text(t("1. 本体を手動で再起動\n2. このアプリでuid=0 / gid=0を確認\n3. Virtual DesktopでPCの映像表示を確認\n\n本体更新の完全防止や将来のアプリ互換性を保証するものではありません。6GHzやスリープの設定はこのウィザードでは変更しません。", "1. Reboot the headset manually\n2. Check uid=0 / gid=0 in this app\n3. Confirm the PC image in Virtual Desktop\n\nComplete firmware-update prevention or future app compatibility is not guaranteed. This wizard does not change sleep or Wi-Fi band settings."),19);
      button(t("Virtual Desktopを開く","Open Virtual Desktop"),new View.OnClickListener(){public void onClick(View v){open("VirtualDesktop.Android","md59102214312e19799944a61bf7bc2f23e.VrActivity");}});
    }
    if(page>0)button(t("戻る","Back"),new View.OnClickListener(){public void onClick(View v){page--;draw();}});
    if(page<4)button(t("次へ","Next"),new View.OnClickListener(){public void onClick(View v){page++;draw();}});
    text(t("プレビュー版 0.1.0 · 通信先は端末内のみ", "Preview 0.1.0 · Helper connections stay on device"),14);
  }
  private void open(String pkg,String cls) {
    try {startActivity(new Intent().setComponent(new ComponentName(pkg,cls)));}
    catch(Exception e){new AlertDialog.Builder(this).setMessage(t("アプリが見つかりません。PC版で導入を確認してください。", "App not found. Check installation in the PC wizard.")).setPositiveButton("OK",null).show();}
  }
  private void diagnose() {
    final TextView target=status;
    new Thread(new Runnable(){public void run(){
      String result;
      try {
        java.lang.Process process=new ProcessBuilder("su","-c","id").redirectErrorStream(true).start();
        if(!process.waitFor(8,TimeUnit.SECONDS)){process.destroyForcibly();throw new IOException("timeout");}
        BufferedReader reader=new BufferedReader(new InputStreamReader(process.getInputStream()));String line=reader.readLine();reader.close();
        boolean ready=process.exitValue()==0 && line!=null && line.contains("uid=0(root)") && line.contains("gid=0(root)");
        result=ready?t("root：確認できました\nuid=0(root) / gid=0(root)","Root verified\nuid=0(root) / gid=0(root)"):t("root：まだ確認できません\n公式アプリのrootとMagiskの許可を確認してください。", "Root not verified yet\nCheck official root and the Magisk permission.");
        boolean disabled=!getPackageManager().getApplicationInfo("com.oculus.updater",0).enabled;
        result+="\n\n"+t("本体更新アプリ：", "Firmware updater: ")+(disabled?t("無効", "disabled"):t("有効（PC版で確認）", "enabled (check on PC)"));
      }catch(Exception e){result=t("状態を取得できません。PC版から診断してください。", "Could not read status. Run diagnostics from the PC wizard.");}
      final String message=result;handler.post(new Runnable(){public void run(){if(target==status && !isFinishing())target.setText(message);}});
    }},"wizard-status").start();
  }
  private void power(final boolean on) {
    confirmAction(on?t("自動スリープを停止し、ボタン操作でのみスリープします。適用しますか？", "Disable automatic sleep and use the power button to sleep. Apply?"):t("自動スリープを60秒に変更します。適用しますか？", "Set automatic sleep to 60 seconds. Apply?"),
      "sh /data/adb/singularity-setup-wizard/power.sh "+(on?"enabled":"disabled"),new Runnable(){public void run(){
        getSharedPreferences("power_settings",0).edit().putBoolean("manual_sleep_only",on).apply();
        if(on)startForegroundService(new Intent(MainActivity.this,AwakeService.class).putExtra("manual_sleep_only",true));
        else stopService(new Intent(MainActivity.this,AwakeService.class));
      }});
  }
  private void confirmAction(String message,final String command,final Runnable success) {
    if(!Compatibility.supported()){new AlertDialog.Builder(this).setMessage(t("未検証の機種・ビルドでは診断のみ利用できます。", "This model/build is unvalidated. Diagnostics only.")).setPositiveButton("OK",null).show();return;}
    new AlertDialog.Builder(this).setMessage(message).setNegativeButton(t("キャンセル","Cancel"),null).setPositiveButton(t("適用","Apply"),new DialogInterface.OnClickListener(){public void onClick(DialogInterface d,int which){
      new Thread(new Runnable(){public void run(){
        boolean ok=false;
        try {java.lang.Process process=new ProcessBuilder("su","-c",command).redirectErrorStream(true).start();
          if(process.waitFor(15,TimeUnit.SECONDS))ok=process.exitValue()==0;else process.destroyForcibly();
        }catch(Exception ignored){}
        final boolean result=ok;
        handler.post(new Runnable(){public void run(){if(isFinishing())return;if(result && success!=null)success.run();new AlertDialog.Builder(MainActivity.this).setMessage(result?t("適用しました。状態確認と実際の動作も確認してください。", "Applied. Check status and actual behavior."):t("適用できませんでした。PC版で導入済みか、rootと6GHz接続を確認してください。", "Could not apply. Check PC setup, root and the current 6GHz connection.")).setPositiveButton("OK",null).show();}});
      }},"wizard-action").start();
    }}).show();
  }
}
