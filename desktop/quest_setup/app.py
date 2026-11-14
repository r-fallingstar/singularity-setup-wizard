from __future__ import annotations
import argparse
import json
from pathlib import Path
import queue
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import webbrowser
from .core import Adb, Installer, Profile, SetupError, find_adb, RELEASES, SINGULARITY, PACKAGE
from .strings import tr
from .extras import enable_wireless, disable_wireless

class Wizard:
    def __init__(self, root, resources, language='ja', demo=False):
        self.root, self.resources, self.lang, self.demo = root, resources, language, demo
        self.step, self.busy = 0, False
        self.events = queue.Queue()
        self.devices = []
        self.last_report = ''
        self.adb_path = tk.StringVar(value=find_adb())
        self.target = tk.StringVar()
        self.apk = tk.StringVar()
        self.auto = tk.BooleanVar(value=True)
        self.remote = tk.BooleanVar(value=False)
        self.ack = tk.BooleanVar(value=False)
        root.title('Singularity Setup Wizard')
        root.geometry('1040x880'); root.minsize(940,820); root.configure(bg='#edf1f3')
        style = ttk.Style(); style.theme_use('clam')
        style.configure('.', font=('Yu Gothic UI', 11), background='#edf1f3', foreground='#192c38')
        style.configure('TButton', padding=(16,10), background='#ffffff')
        style.configure('Accent.TButton', background='#136d83', foreground='white')
        style.configure('TCheckbutton', padding=8)
        style.configure('TEntry', padding=7)
        self.draw(); root.after(100,self.poll)
    def t(self,key): return tr(key,self.lang)
    def label(self,parent,text,size=11,color='#415562',wrap=690):
        w=tk.Label(parent,text=text,bg='#edf1f3',fg=color,font=('Yu Gothic UI',size),justify='left',anchor='w',wraplength=wrap)
        w.pack(fill='x',pady=(0,18)); return w
    def button(self,parent,key,fn,accent=False):
        b=ttk.Button(parent,text=self.t(key),command=fn,style='Accent.TButton' if accent else 'TButton')
        b.pack(anchor='w',pady=5); return b
    def draw(self):
        for w in self.root.winfo_children(): w.destroy()
        top=tk.Frame(self.root,bg='#edf1f3'); top.pack(fill='x',padx=32,pady=(22,14))
        tk.Label(top,text='Singularity Setup Wizard',font=('Segoe UI',19,'bold'),bg='#edf1f3',fg='#192c38').pack(side='left')
        lang=ttk.Combobox(top,values=['日本語','English'],state='readonly',width=10)
        lang.set('日本語' if self.lang=='ja' else 'English'); lang.pack(side='right')
        lang.bind('<<ComboboxSelected>>',lambda e:self.language(lang.get()))
        body=tk.Frame(self.root,bg='#edf1f3'); body.pack(fill='both',expand=True,padx=32)
        side=tk.Frame(body,bg='#edf1f3',width=205); side.pack(side='left',fill='y',padx=(0,22)); side.pack_propagate(False)
        self.label(side,self.t('subtitle'),10,wrap=190)
        for i,name in enumerate(self.t('steps').split('|')):
            self.label(side,f'{i+1:02d}   {name}',12,'#136d83' if i==self.step else '#7a8992',wrap=195)
        self.label(side,self.t('preview'),10,wrap=190)
        panel=tk.Frame(body,bg='#edf1f3'); panel.pack(side='left',fill='both',expand=True)
        headings=['welcome','connect','official','options','review','result']
        self.label(panel,self.t(headings[self.step]),23,'#192c38')
        if self.step==0:
            self.label(panel,self.t('intro'),12); self.label(panel,self.t('scope'),11,'#136d83')
        elif self.step==1:
            self.label(panel,self.t('connect_help'))
            self.label(panel,self.t('adb'),10)
            ttk.Entry(panel,textvariable=self.adb_path).pack(fill='x')
            self.button(panel,'browse',self.pick_adb)
            self.button(panel,'scan',lambda:self.work(self.scan))
            self.label(panel,self.t('device'),10)
            self.device_box=ttk.Combobox(panel,textvariable=self.target,values=[f'{s} [{st}]' for s,st in self.devices],state='readonly')
            self.device_box.pack(fill='x',pady=5)
            self.button(panel,'diagnose',lambda:self.work(lambda:self.adb().inspect()))
        elif self.step==2:
            self.label(panel,self.t('official_help'))
            self.button(panel,'releases',lambda:webbrowser.open(RELEASES))
            ttk.Entry(panel,textvariable=self.apk).pack(fill='x',pady=5)
            self.button(panel,'browse',self.pick_apk)
            self.button(panel,'install_official',self.install_official)
            self.button(panel,'launch_official',lambda:self.work(lambda:self.adb().launch(SINGULARITY)))
        elif self.step==3:
            self.fixed=tk.BooleanVar(value=True)
            ttk.Checkbutton(panel,text=self.t('firmware'),variable=self.fixed,state='disabled').pack(anchor='w',pady=8)
            ttk.Checkbutton(panel,text=self.t('auto_root'),variable=self.auto).pack(anchor='w',pady=8)
            ttk.Checkbutton(panel,text=self.t('remote'),variable=self.remote).pack(anchor='w',pady=8)
            self.label(panel,self.t('options_help'),11)
        elif self.step==4:
            for key,on in [('firmware',True),('auto_root',self.auto.get()),('remote',self.remote.get())]:
                self.label(panel,('ON  ' if on else 'OFF  ')+self.t(key),12)
            self.label(panel,self.target.get() or self.t('select'),10,'#136d83')
            self.label(panel,self.t('review_help'),10)
            ttk.Checkbutton(panel,text=self.t('ack'),variable=self.ack,command=self.toggle_apply).pack(anchor='w')
            self.apply_button=self.button(panel,'apply',self.apply,True); self.toggle_apply()
            self.button(panel,'restore',self.restore)
        else:
            self.label(panel,self.t('result_help'))
            self.label(panel,self.t('extras_help'),10)
            self.button(panel,'check',lambda:self.work(lambda:self.adb().inspect()))
            self.button(panel,'launch_companion',lambda:self.work(lambda:self.adb().launch(PACKAGE)))
            self.button(panel,'wireless_on',self.wireless)
            self.button(panel,'wireless_off',self.stop_wireless)
            self.button(panel,'restore',self.restore)
        self.output=tk.Text(panel,height=5,wrap='word',relief='flat',bg='#ffffff',fg='#243e4b',font=('Yu Gothic UI',10),padx=14,pady=12)
        self.output.pack(fill='both',expand=True,pady=(12,8)); self.show(self.last_report)
        nav=tk.Frame(self.root,bg='#edf1f3'); nav.pack(side='bottom',before=body,fill='x',padx=32,pady=18)
        self.prev=ttk.Button(nav,text=self.t('back'),command=lambda:self.go(-1)); self.prev.pack(side='left')
        self.next=ttk.Button(nav,text=self.t('next'),command=lambda:self.go(1),style='Accent.TButton'); self.next.pack(side='right')
        self.prev.configure(state='disabled' if self.step==0 or self.busy else 'normal')
        self.next.configure(state='disabled' if self.step>=4 or self.busy else 'normal')
        if self.busy:
            for child in panel.winfo_children():
                if isinstance(child,(ttk.Button,ttk.Combobox,ttk.Checkbutton,ttk.Entry)): child.configure(state='disabled')
            lang.configure(state='disabled')
    def language(self,value): self.lang='ja' if value=='日本語' else 'en'; self.draw()
    def go(self,delta):
        if self.busy:return
        self.step=max(0,min(5,self.step+delta)); self.draw()
    def show(self,value):
        text=json.dumps(value,ensure_ascii=False,indent=2) if isinstance(value,dict) else str(value)
        self.last_report=text
        self.output.configure(state='normal'); self.output.delete('1.0','end'); self.output.insert('1.0',text); self.output.configure(state='disabled')
    def adb(self):
        if self.demo: raise SetupError('Preview mode: device changes are disabled.')
        chosen=self.target.get()
        match=next((s for s,st in self.devices if chosen==f'{s} [{st}]' and st=='device'),None)
        if not match:raise SetupError(self.t('select'))
        if not Path(self.adb_path.get()).is_file():raise SetupError('ADB executable was not found.')
        return Adb(self.adb_path.get(),match)
    def scan(self):
        if self.demo:return {'demo':True}
        devices=Adb(self.adb_path.get()).devices()
        self.events.put(('devices',devices))
        return self.t('no_devices') if not devices else self.t('select')
    def pick_adb(self):
        name=filedialog.askopenfilename(filetypes=[('ADB','adb.exe'),('All files','*')])
        if name:self.adb_path.set(name)
    def pick_apk(self):
        name=filedialog.askopenfilename(filetypes=[('Android APK','*.apk')])
        if name:self.apk.set(name)
    def install_official(self):
        # Selection is explicit; do not replace an installed app with arbitrary package identity.
        self.work(lambda:self.adb().install_official(self.apk.get()))
    def toggle_apply(self):
        self.apply_button.configure(state='normal' if self.ack.get() and not self.busy else 'disabled')
    def apply(self):
        if not self.ack.get() or self.busy:return
        profile=Profile(auto_root=self.auto.get(),remote_actions=self.remote.get())
        self.work(lambda:Installer(self.adb(),self.resources).apply(profile,lambda k:self.events.put(('progress',self.t(k)))),applied=True)
    def restore(self):
        if messagebox.askyesno(self.t('restore'),self.t('restore_confirm')):
            self.work(lambda:Installer(self.adb(),self.resources).restore())
    def wireless(self):
        if self.demo:return self.show('Preview mode: changes are disabled.')
        if messagebox.askyesno(self.t('wireless_on'),self.t('wireless_confirm')):
            self.work(lambda:enable_wireless(self.adb()))
    def stop_wireless(self):
        if self.demo:return self.show('Preview mode: changes are disabled.')
        self.work(disable_wireless)
    def work(self,fn,applied=False):
        if self.busy:return
        self.busy=True; self.last_report=self.t('busy'); self.draw()
        def run():
            try:self.events.put(('applied' if applied else 'result',fn()))
            except Exception as exc:self.events.put(('error',str(exc)))
        threading.Thread(target=run,daemon=True).start()
    def poll(self):
        try:
            while True:
                kind,value=self.events.get_nowait()
                if kind=='devices':
                    self.devices=value
                    ready=[s for s,st in value if st=='device']
                    if len(ready)==1:self.target.set(ready[0]+' [device]')
                elif kind=='progress':self.show(value)
                else:
                    self.busy=False
                    if kind=='applied':self.step=5
                    self.last_report=(self.t('error')+'\n'+value) if kind=='error' else value
                    self.draw()
        except queue.Empty:pass
        self.root.after(100,self.poll)

def main():
    p=argparse.ArgumentParser();p.add_argument('--lang',choices=['ja','en'],default='ja');p.add_argument('--preview',action='store_true');p.add_argument('--preview-step',type=int,default=0)
    p.add_argument('--watch',action='store_true')
    args=p.parse_args()
    if args.watch:
        from .wireless import main as watch
        raise SystemExit(watch([]))
    resources=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parents[2]))
    root=tk.Tk();app=Wizard(root,resources,args.lang,args.preview)
    if args.preview:app.step=max(0,min(5,args.preview_step));app.draw()
    root.mainloop()
