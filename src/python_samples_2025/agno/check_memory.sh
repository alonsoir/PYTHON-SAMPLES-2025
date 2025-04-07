#!/bin/zsh

sysctl hw.memsize

top -l 1 -s 0 | grep PhysMem

top -l 1 | grep PhysMem
free