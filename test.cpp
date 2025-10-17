#include<iostream>
#include<unordered_map>
#include<functional>
#include<string>
#include<sstream>
#include<vector>
#include<cstdlib>
#include<unistd.h>

using namespace std;
unordered_map<string, function<void(string)>> commands;
void exitShell(string command){
    if(command == "exit"){
            exit(0);
        }
}

void echo(string command){
    stringstream ss(command);
    vector<string> str;
    string word;
    while(ss >> word){
        str.push_back(word);
    }
    str.erase(str.begin());

    for(string s : str){
        cout<<s<<" ";
    }
    cout<<endl;
}

void typeOfCommand(string command){
    stringstream ss(command);
    vector<string> str;
    string word;
    while(ss >> word){
        str.push_back(word);
    }
    
    bool exist=false;
    if(str.size()<=1)
    {
        return;
    }

    if(str.size()>1){
        auto it = commands.find(str[1]);
        if(it != commands.end())
        {
            cout<<str[1]<<" is a shell builtin"<<endl;
            exist=true;
        }
    }    
        if(!exist)
        {
            char* path=getenv("PATH");
            if(path!=NULL)
            {
                string spath(path);
                string directory="";
                for(int i=0;i<=spath.length();i++)
                {
                    if(i==spath.length()||spath[i]==':')
                    {
                        if(!directory.empty())
                        {
                            string fullpath= directory +"/"+str[1];
                            if(access(fullpath.c_str(),X_OK) == 0){
                                cout<<fullpath<<endl;
                                exist=true;
                            }
                        }
                        directory.clear();
                    }
                    else
                    {
                        directory+=spath[i];
                    }
                }
            }

            if(!exist)
               cout<< str[1] <<": command not found\n";
        }
}

void cd(string command)
{
    stringstream ss(command);
    vector<string> str;
    string word;
    while(ss >> word){
        str.push_back(word);
    }
    str.erase(str.begin());
    if(str.size()<1)
    {
        return;
    }
    if(str[0]=="~")
    {
        char*path=getenv("HOME");
        str[0]=path;
    }
    if(chdir(str[0].c_str())!=0)
    {
        cout<<"cd: "<<str[0]<<": No such file or directory"<<endl;
    }
}

void pwd(string command) {
    char cwd[1000];
    getcwd(cwd,sizeof(cwd));
    cout << cwd << endl;
}

void run_exec(string command){
    pid_t pid = fork();
    stringstream ss(command);
    vector<string> str;
    string word;

    while(ss >> word){
        str.push_back(word);
    }

    int n = str.size();
    char *args[n+1];

    for(int i=0;i<n;i++){
        args[i] = (char *)str[i].c_str();
    }
    args[n] = NULL;

    if(pid>0){
        wait(NULL);
    }
    else if(pid==0){
        if(args[0][0]=='.' && args[0][1]=='/'){
            execv(args[0], args);
            perror("execv");
        }
        else{
            int is_err = execvp(args[0], args);
            if(is_err == -1){
                cout<< str[0] <<": command not found\n";
            }
        }
    }
}

int main(){
    string command;
    commands ={
        {"exit", exitShell},
        {"echo", echo},
        {"type", typeOfCommand},
        {"cd", cd},
        {"pwd", pwd},
    };

    
    while(true){
        cout << "aurashell$ ";
        getline(cin, command);

        if(command==""){
            continue;
        }
        string str="";
        int i=0;
        while(command[i] != ' ' && i<command.length()){
            str=str+command[i++];
        }

        auto it = commands.find(str);

        if(it != commands.end()){
            it->second(command);
        }
        else {
            run_exec(command);
            cout<<endl;
        }
    }
}
