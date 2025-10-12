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
            if(it->first == "exit" || it->first == "echo" || it->first == "type"){
            cout<<str[1]<<" is a shell builtin"<<endl;
            exist=true;
            }
        }
    }    
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
            {
               cout<< str[1] <<": command not found\n";
            }
}
int main(){
    string command;
    commands ={
        {"exit", exitShell},
        {"echo", echo},
        {"type", typeOfCommand}
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
        else{
            cout<< str <<": command not found\n";
        }
    }
}