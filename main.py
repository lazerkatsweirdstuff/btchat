import tkinter as tk
from tkinter import scrolledtext, messagebox, filedialog, ttk
import bluetooth
import threading
import os
import sys
from time import sleep

class BluetoothChat:
    def __init__(self, root):
        self.root = root
        self.root.title("Bluetooth Chat")
        
        # Bluetooth variables
        self.server_sock = None
        self.client_sock = None
        self.connected = False
        self.current_file_transfer = None
        
        # Setup GUI
        self.setup_gui()
        
        # Start Bluetooth discovery
        self.discover_devices()
    
    def setup_gui(self):
        # Main frame
        main_frame = tk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Left panel (devices)
        left_panel = tk.Frame(main_frame, width=200, bd=2, relief=tk.RIDGE)
        left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 5))
        left_panel.pack_propagate(False)
        
        # Device list
        tk.Label(left_panel, text="Available Devices").pack(pady=5)
        self.device_list = ttk.Treeview(left_panel, columns=('name', 'address'), show='headings')
        self.device_list.heading('name', text='Device Name')
        self.device_list.heading('address', text='Address')
        self.device_list.column('name', width=120)
        self.device_list.column('address', width=80)
        self.device_list.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.device_list.bind('<Double-1>', self.connect_to_device)
        
        # Refresh button
        refresh_btn = tk.Button(left_panel, text="Refresh Devices", command=self.discover_devices)
        refresh_btn.pack(pady=5, padx=5, fill=tk.X)
        
        # Host button
        host_btn = tk.Button(left_panel, text="Host Chat", command=self.host_chat)
        host_btn.pack(pady=5, padx=5, fill=tk.X)
        
        # Right panel (chat)
        right_panel = tk.Frame(main_frame, bd=2, relief=tk.RIDGE)
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # Chat display
        self.chat_display = scrolledtext.ScrolledText(right_panel, state='disabled')
        self.chat_display.pack(padx=5, pady=5, fill=tk.BOTH, expand=True)
        
        # Message frame
        msg_frame = tk.Frame(right_panel)
        msg_frame.pack(padx=5, pady=(0, 5), fill=tk.X)
        
        # Message entry
        self.message_entry = tk.Entry(msg_frame)
        self.message_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.message_entry.bind("<Return>", self.send_message)
        
        # Send button
        send_btn = tk.Button(msg_frame, text="Send", command=self.send_message)
        send_btn.pack(side=tk.RIGHT, padx=(5, 0))
        
        # File transfer frame
        file_frame = tk.Frame(right_panel)
        file_frame.pack(padx=5, pady=(0, 5), fill=tk.X)
        
        # File buttons
        send_file_btn = tk.Button(file_frame, text="Send File", command=self.send_file_dialog)
        send_file_btn.pack(side=tk.LEFT)
        
        # Status bar
        self.status_var = tk.StringVar()
        self.status_var.set("Not connected")
        status_bar = tk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Transfer progress
        self.progress_var = tk.DoubleVar()
        progress_bar = ttk.Progressbar(self.root, variable=self.progress_var, maximum=100)
        progress_bar.pack(side=tk.BOTTOM, fill=tk.X)
    
    def discover_devices(self):
        """Discover nearby Bluetooth devices"""
        self.status_var.set("Discovering nearby devices...")
        
        def discovery_thread():
            try:
                nearby_devices = bluetooth.discover_devices(lookup_names=True, duration=8)
                self.device_list.delete(*self.device_list.get_children())
                for addr, name in nearby_devices:
                    self.device_list.insert('', 'end', values=(name, addr))
                self.status_var.set("Found {} devices".format(len(nearby_devices)))
            except Exception as e:
                self.status_var.set("Discovery error: {}".format(str(e)))
        
        threading.Thread(target=discovery_thread, daemon=True).start()
    
    def connect_to_device(self, event):
        """Connect to the selected device"""
        if self.connected:
            messagebox.showwarning("Warning", "Already connected. Disconnect first.")
            return
            
        selected = self.device_list.focus()
        if not selected:
            return
            
        device = self.device_list.item(selected)['values']
        addr = device[1]
        
        try:
            self.client_sock = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
            self.client_sock.connect((addr, 1))
            self.connected = True
            self.status_var.set("Connected to {}".format(device[0]))
            
            # Start thread to receive messages
            threading.Thread(target=self.receive_messages, daemon=True).start()
        except Exception as e:
            messagebox.showerror("Error", "Could not connect: {}".format(str(e)))
            self.status_var.set("Connection failed")
    
    def host_chat(self):
        """Host a Bluetooth chat server"""
        if self.connected:
            messagebox.showwarning("Warning", "Already connected. Disconnect first.")
            return
            
        self.server_sock = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
        self.server_sock.bind(("", bluetooth.PORT_ANY))
        self.server_sock.listen(1)
        
        port = self.server_sock.getsockname()[1]
        uuid = "00001101-0000-1000-8000-00805F9B34FB"
        
        bluetooth.advertise_service(
            self.server_sock, "BluetoothChat",
            service_id=uuid,
            service_classes=[uuid, bluetooth.SERIAL_PORT_CLASS],
            profiles=[bluetooth.SERIAL_PORT_PROFILE]
        )
        
        self.status_var.set("Waiting for connection on RFCOMM channel {}...".format(port))
        
        # Start thread to accept connections
        threading.Thread(target=self.accept_connections, daemon=True).start()
    
    def accept_connections(self):
        """Accept incoming connections"""
        try:
            self.client_sock, client_info = self.server_sock.accept()
            self.connected = True
            self.status_var.set("Connected to {}".format(client_info[0]))
            
            # Start thread to receive messages
            threading.Thread(target=self.receive_messages, daemon=True).start()
        except Exception as e:
            self.status_var.set("Connection error: {}".format(str(e)))
    
    def disconnect(self):
        """Disconnect from current connection"""
        if not self.connected:
            return
            
        try:
            if self.client_sock:
                self.client_sock.close()
            if self.server_sock:
                self.server_sock.close()
        except:
            pass
            
        self.connected = False
        self.client_sock = None
        self.server_sock = None
        self.status_var.set("Disconnected")
    
    def send_message(self, event=None):
        """Send a message through the Bluetooth connection"""
        if not self.connected:
            messagebox.showwarning("Warning", "Not connected to any device.")
            return
            
        message = self.message_entry.get()
        if not message:
            return
            
        try:
            # Prepend 'M:' to indicate it's a message (not file data)
            self.client_sock.send("M:{}".format(message).encode('utf-8'))
            self.display_message("You", message)
            self.message_entry.delete(0, tk.END)
        except Exception as e:
            self.status_var.set("Error sending message: {}".format(str(e)))
            self.disconnect()
    
    def send_file_dialog(self):
        """Open file dialog to select file to send"""
        if not self.connected:
            messagebox.showwarning("Warning", "Not connected to any device.")
            return
            
        filename = filedialog.askopenfilename()
        if not filename:
            return
            
        try:
            # Send file in a separate thread
            threading.Thread(
                target=self.send_file, 
                args=(filename,),
                daemon=True
            ).start()
        except Exception as e:
            messagebox.showerror("Error", "Failed to send file: {}".format(str(e)))
    
    def send_file(self, filename):
        """Send a file through the Bluetooth connection"""
        try:
            filesize = os.path.getsize(filename)
            basename = os.path.basename(filename)
            
            # Send file header (F:filename:filesize)
            header = "F:{}:{}".format(basename, filesize)
            self.client_sock.send(header.encode('utf-8'))
            
            # Wait for acknowledgment
            ack = self.client_sock.recv(1024).decode('utf-8')
            if ack != "ACK":
                raise Exception("Receiver didn't acknowledge file transfer")
            
            # Send file data
            self.status_var.set("Sending {}...".format(basename))
            self.current_file_transfer = basename
            
            with open(filename, 'rb') as f:
                sent = 0
                while sent < filesize:
                    chunk = f.read(1024)
                    self.client_sock.send(chunk)
                    sent += len(chunk)
                    self.progress_var.set((sent / filesize) * 100)
                    self.root.update()
            
            self.display_message("You", "Sent file: {}".format(basename))
            self.status_var.set("File sent successfully")
            self.progress_var.set(0)
            self.current_file_transfer = None
            
        except Exception as e:
            self.status_var.set("File transfer error: {}".format(str(e)))
            self.progress_var.set(0)
            self.current_file_transfer = None
            if self.connected:  # Only disconnect if connection is still active
                self.disconnect()
    
    def receive_messages(self):
        """Receive messages from the Bluetooth connection"""
        buffer = b""
        
        while self.connected:
            try:
                data = self.client_sock.recv(1024)
                if not data:
                    break
                
                buffer += data
                
                # Check if we have a complete message
                while buffer:
                    # Check for file header
                    if buffer.startswith(b"F:"):
                        # Find the end of header (second colon)
                        header_end = buffer.find(b":", 2)
                        if header_end == -1:
                            break  # Incomplete header
                        
                        filesize_end = buffer.find(b":", header_end + 1)
                        if filesize_end == -1:
                            break  # Incomplete header
                        
                        filename = buffer[2:header_end].decode('utf-8')
                        filesize = int(buffer[header_end+1:filesize_end].decode('utf-8'))
                        
                        # Check if we have the complete header + some data
                        if len(buffer) < filesize_end + 1 + filesize:
                            break  # Not all data received yet
                        
                        # Send ACK
                        self.client_sock.send(b"ACK")
                        
                        # Extract file data
                        file_data = buffer[filesize_end+1:filesize_end+1+filesize]
                        buffer = buffer[filesize_end+1+filesize:]
                        
                        # Save file
                        self.save_file(filename, file_data)
                        continue
                    
                    # Check for regular message
                    elif buffer.startswith(b"M:"):
                        msg_end = buffer.find(b"\n", 2)
                        if msg_end == -1:
                            break  # Incomplete message
                        
                        message = buffer[2:msg_end].decode('utf-8')
                        buffer = buffer[msg_end+1:]
                        
                        self.display_message("Partner", message)
                        continue
                    
                    # If we get here, it's not a recognized message type
                    break
                
            except Exception as e:
                if self.connected:  # Only show error if we didn't disconnect intentionally
                    self.root.after(0, lambda: self.status_var.set("Connection lost: {}".format(str(e))))
                break
                
        self.root.after(0, self.disconnect)
    
    def save_file(self, filename, data):
        """Save received file with confirmation"""
        save_path = filedialog.asksaveasfilename(
            initialfile=filename,
            title="Save received file"
        )
        
        if not save_path:
            self.display_message("System", "File transfer canceled by user")
            return
            
        try:
            with open(save_path, 'wb') as f:
                f.write(data)
            
            self.display_message("Partner", "Sent file: {}".format(filename))
            self.status_var.set("File received successfully")
        except Exception as e:
            self.display_message("System", "Failed to save file: {}".format(str(e)))
    
    def display_message(self, sender, message):
        """Display a message in the chat window"""
        self.chat_display.configure(state='normal')
        self.chat_display.insert(tk.END, "{}: {}\n".format(sender, message))
        self.chat_display.configure(state='disabled')
        self.chat_display.see(tk.END)
    
    def on_closing(self):
        """Clean up when closing the application"""
        self.disconnect()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = BluetoothChat(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()
