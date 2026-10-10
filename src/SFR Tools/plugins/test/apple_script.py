import subprocess
script = """
tell application "System Events"
    tell process "KiCad"
        set frontmost to true

        repeat with w in every window
            -- Make this the active window
            perform action "AXRaise" of w

            try
                set value of attribute "AXFocused" of w to true
            end try

            if exists menu "File" of menu bar 1 then
                set fileMenu to menu "File" of menu bar 1

                if exists menu item "Save" of fileMenu then
                    set saveItem to menu item "Save" of fileMenu

                    if enabled of saveItem then
                        click saveItem

                    end if
                end if
            end if
        end repeat
    end tell
end tell"""

subprocess.run(
    ["osascript", "-e", script],
    check=True
)