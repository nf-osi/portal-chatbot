#!/bin/bash

jq -r '.response.body.choices[0].message.content' $1 > $2
