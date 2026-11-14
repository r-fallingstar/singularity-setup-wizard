import android.content.Context;
import android.net.wifi.WifiConfiguration;
import android.net.wifi.WifiManager;
import android.os.Looper;
import java.lang.reflect.Method;
import java.util.List;

public class QuestWifiAdmin {
    public static void main(String[] args) {
        try { run(args); System.exit(0); }
        catch (Exception e) { e.printStackTrace(); System.exit(1); }
    }
    private static void run(String[] args) throws Exception {
        Looper.prepareMainLooper();
        Class<?> at = Class.forName("android.app.ActivityThread");
        Object thread = at.getMethod("systemMain").invoke(null);
        Context context = (Context) at.getMethod("getSystemContext").invoke(thread);
        WifiManager wifi = (WifiManager) context.getSystemService(Context.WIFI_SERVICE);
        List<WifiConfiguration> configs = wifi.getConfiguredNetworks();
        if (configs == null) throw new IllegalStateException("No configured networks returned");
        if (args.length == 0 || args[0].equals("list")) {
            for (WifiConfiguration c : configs) print(c);
            return;
        }
        if(args[0].equals("pin-current")) {
            android.net.wifi.WifiInfo current=wifi.getConnectionInfo();
            if(current.getFrequency()<5925 || current.getFrequency()>7125)throw new IllegalStateException("Current connection is not 6GHz");
            String ssid=current.getSSID();
            args=new String[]{"pin",Integer.toString(current.getNetworkId()),ssid.substring(1,ssid.length()-1),current.getBSSID()};
        }
        int id = Integer.parseInt(args[1]);
        String expected = "\"" + args[2] + "\"";
        WifiConfiguration found = null;
        for (WifiConfiguration c : configs) if (c.networkId == id && expected.equals(c.SSID)) found = c;
        if (found == null) throw new IllegalArgumentException("Network identity mismatch");
        if (args[0].equals("pin")) {
            String bssid = args[3];
            if (!bssid.matches("(?i)([0-9a-f]{2}:){5}[0-9a-f]{2}")) throw new IllegalArgumentException("Invalid BSSID");
            // Use the returned configuration so default security fields cannot replace it.
            // Android treats the masked saved password as "keep existing credential".
            WifiConfiguration patch = new WifiConfiguration(found);
            WifiConfiguration.class.getMethod("setSecurityParams", int.class).invoke(patch, 4);
            patch.BSSID = bssid;
            int result = wifi.updateNetwork(patch);
            if (result != id) throw new IllegalStateException("updateNetwork failed: " + result);
            System.out.println("Pinned network " + id + " to " + bssid);
        } else if (args[0].equals("autojoin")) {
            Method m = WifiManager.class.getMethod("allowAutojoin", int.class, boolean.class);
            m.invoke(wifi, id, Boolean.parseBoolean(args[3]));
            System.out.println("Autojoin updated for network " + id);
        } else if (args[0].equals("remove")) {
            if (!wifi.removeNetwork(id)) throw new IllegalStateException("removeNetwork failed");
            System.out.println("Removed test network " + id);
        } else if (args[0].equals("connect")) {
            Method m = WifiManager.class.getMethod("connect", int.class, Class.forName("android.net.wifi.WifiManager$ActionListener"));
            m.invoke(wifi, id, null);
            System.out.println("Connection requested for network " + id);
        } else throw new IllegalArgumentException("Unknown action");
        for (WifiConfiguration c : wifi.getConfiguredNetworks()) if (c.networkId == id) print(c);
    }
    private static void print(WifiConfiguration c) throws Exception {
        System.out.println("id=" + c.networkId + " ssid=" + c.SSID + " bssid=" + c.BSSID
            + " autojoin=" + WifiConfiguration.class.getField("allowAutojoin").getBoolean(c)
            + " keyManagement=" + c.allowedKeyManagement);
    }
}
