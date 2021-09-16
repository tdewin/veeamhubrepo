from dialog import Dialog
import os
import getpass


def screensize():
    srows,scolumns = os.popen('stty size','r').read().split()
    return int(srows),int(scolumns)

class DialogWrapper:
    OK=1
    title=""
    Cancel=-1
    style="dialog"

    def __init__(self,title):
        self.title = "VeeamHub Tiny Repo Manager"
        self.dialog = Dialog(dialog="dialog")
        self.dialog.set_background_title(self.title)
        self.OK = self.dialog.OK

    def infobox(self,infotext,width=80,height=10):
        return self.dialog.infobox(infotext,width=width,height=height)
    
    def msgbox(self,infotext,width=80,height=10):
        return self.dialog.msgbox(infotext,width=width,height=height)
    

    def passwordbox(self,infotext,insecure=True):
        return self.dialog.passwordbox(infotext,insecure=insecure)

    def inputbox(self,infotext,init=""):
        return self.dialog.inputbox(infotext,init=init,width=80)

    def yesno(self,question,width=80,height=10,yes_label="yes",no_label="no"):
        return self.dialog.yesno(question,width=80,height=10,yes_label=yes_label,no_label=no_label)
    
    def menu(self,text,choices,height=15,cancel="Cancel"):
        return self.dialog.menu(text,choices=choices,height=height,cancel=cancel)

    def checklist(self,text,choices,height=15,cancel="Cancel"):
        return self.dialog.checklist(text,choices=choices,height=height,cancel=cancel)

    def fselect(self,path,width=80,height=20):
        self.msgbox("Easiest way is to type the path while browsing\nUse / as dir seperator\n\nAlternatively try tab+arrow keys to navigate\nand space to copy",width=60)
        return self.dialog.fselect(path,width=width,height=height)


class AlternateDialog(DialogWrapper):
    style="alternate"
    rows=0
    columns=0

    def __init__(self,title,rows,columns):
        self.rows = rows
        self.columns = columns
        DialogWrapper.__init__(self,title)
    
    def header(self):
        print("{}".format(self.title))

    def lnspacer(self):
        dasher = []
        dash = "-"
        for i in range(int(self.columns/4*3)):
            dasher.append(dash)
        print("".join(dasher))

    def cls(self):
        os.system('clear')
        self.rows,self.columns = screensize()
        self.header()
        self.lnspacer()


    def passwordbox(self,infotext,insecure=True):
        self.cls()
        print(infotext)
        self.lnspacer()
        passw = getpass.getpass(prompt="password : ")
        return self.OK,passw


    def infobox(self,infotext,width=80,height=10):
        self.cls()
        print(infotext)
        self.lnspacer()
    
    def yesno(self,question,width=80,height=10,yes_label="yes",no_label="no"):
        code = self.OK
        test = "o"
        while not (test == "" or test == "e"):
            self.cls()
            print(question)
            self.lnspacer()
            test = input("Press <<enter>> for {}, enter <<e>> for {} : ".format(yes_label,no_label))
        if test == "e":
            code = self.Cancel
        return code

    def msgbox(self,infotext,width=80,height=10):
        self.cls()
        print(infotext)
        self.lnspacer()
        input("Press enter to continue..")
    
    def inputbox(self,infotext,init=""):
        self.cls()
        print(infotext)
        self.lnspacer()
        code = self.OK
        answer = ""
        try:
            answer = input("(default <<{}>>, ctrl+c to exit): ".format(init))
            if answer == "":
                answer = init
        except KeyboardInterrupt:
            code = self.Cancel

        return code,answer

    def menu(self,text,choices,height=15,cancel="Cancel"):
        valid = ["e"]
        for c in choices:
            valid.append(c[0])
        
        userinput = ""
        while not userinput in valid:
            self.cls()
            print(text)
            self.lnspacer()
            for c in choices:
                print("{}) {}".format(c[0],c[1]))
            self.lnspacer()
            userinput = input("Please specify choice or <<e>> to exit:")

        code = self.OK
        if userinput == "e":
            code = self.Cancel

        return code,userinput
    
    def checklist(self,text,choices,height=15,cancel="Cancel"):
        valid = ["e"]
        for c in choices:
            valid.append(c[0])

        userinput = ""
        expl = []
        allvalid = False
        while not allvalid:
            self.cls()
            print(text)
            self.lnspacer()
            for c in choices:
                print("{}) {}".format(c[0],c[1]))
            self.lnspacer()
            print("Multi select by using ',' as a seperator e.g 1,2")
            userinput = input("Please specify choice or <<e>> to exit:")
            expl = userinput.split(",")
            testvalid = True
            for t in expl:
                if not t in valid:
                    testvalid = False
            if testvalid and len(expl) > 0:
                allvalid = True

        code = self.OK
        if userinput == "e":
            code = self.Cancel

        return code,expl
    

            
    def fselect(self,path,width=80,height=20):
        self.cls()
        path = path.rstrip("/")
        print("Current path is {}".format(path))
        filesall = []
        fileindex = {}
        selecti = 1
        for dirwalk in os.walk(path):
            for fwalk in dirwalk[2]:
                localpath = dirwalk[0].replace(path,"")
                fname = fwalk
                if localpath != "":
                    fname = "{}/{}".format(dirwalk[0].replace(path,""),fwalk)
                
                fobject = [fname,"{}/{}".format(dirwalk[0],fwalk),selecti]
                filesall.append(fobject)
                fileindex[selecti]=fobject 
                selecti = selecti+1

        selected = -1
        showing = 0
        maxln = self.rows-5
        if maxln < 15:
            maxln = 20

        search = ""
        
        filteredfiles = filesall

        while selected == -1:
            showingend = showing + maxln
            nextround = showingend
            #if we are the end of the file list
            if showingend >= len(filteredfiles):
                showingend = len(filteredfiles)
                nextround = 0
            
            for i in range(showing,showingend):
                print("{}) {}".format(filteredfiles[i][2],filteredfiles[i][0]))
            

            if search == "":
                print("Use /<search> e.g /myfile to filter for a specific file")
            else:
                print("Current search is {}, use / to reset".format(search))

            selecttest = input("Please number to select or enter for more ({}) : ".format(len(filteredfiles)))
            if selecttest != "":
                if selecttest == "e":
                    return self.Cancel,""
                elif selecttest[0] == "/":
                    search = selecttest[1:].strip()
                    if search == "":
                        filteredfiles = filesall
                    else:
                        filteredfiles = []
                        for f in filesall:
                            if search in f[1]:
                                filteredfiles.append(f)
                    nextround = 0
                else:
                    try:
                        intval = int(selecttest)
                        if intval in fileindex:
                            selected = fileindex[intval]
                    except ValueError:
                            print("Please enter an integer or hit enter to see more")
            
            showing = nextround
        
        fileselected = selected[1]
        code = self.yesno("Selecting {}".format(fileselected))
        
        return code,fileselected
