import tkinter as tk
from tkinter import ttk


def main():
    root = tk.Tk()
    root.title("assu_genfli")
    root.minsize(400, 200)

    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)

    # Frame
    frame = ttk.LabelFrame(root, padding=20)
    frame.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
    frame.columnconfigure(0, weight=1)
    frame.rowconfigure(0, weight=1)

    # Label Hello World
    label = ttk.Label(frame, text="Hello World", font=("Segoe UI", 18, "bold"))
    label.grid(row=0, column=0)

    root.mainloop()


if __name__ == "__main__":
    main()
